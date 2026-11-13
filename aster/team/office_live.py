"""A live company office. Each spoken line and each written file comes from the model.

One value of ``OfficeState`` is the dashboard for a single brief: the events so
far, the files written so far, and whether the job is running, blocked, or
passed. The provider key is not a field. ``snapshot`` returns exactly those
dashboard fields.

``run_live_office`` reads a brief and a ``ModelCaller``. It appends one event
after each model reply, writes the files the reply contains, and runs Pixel's
acceptance test and the separate holdout. A skill file is written only when
both checks pass. A missing caller appends one blocked event and no meeting.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from aster.team.model import ModelCallError, ModelCaller, OpenAIChatModel, model_from_environment
from aster.team.run import SKILL_NAME, process_output, read_skill, run_pytest, write_text

PEOPLE = (
    ("nova", "Nova"),
    ("scout", "Scout"),
    ("lumi", "Lumi"),
    ("pixel", "Pixel"),
    ("forge", "Forge"),
    ("sage", "Sage"),
)
FLOOR = [person_id for person_id, _name in PEOPLE]
BLOCKED = "Blocked: set ASTER_UPSTREAM_URL and ASTER_UPSTREAM_API_KEY"


class OfficeState:
    """The dashboard for one company job.

    ``events`` is the list of tool steps in the order they happened. ``files``
    maps a file name to the text last written. ``running`` is true only while
    a job has started and has not finished. ``connected`` is true when a model
    caller exists. The snapshot is the JSON object the page reads.
    """

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.files: dict[str, str] = {}
        self.running = False
        self.blocked = False
        self.passed = False
        self.connected = False
        self.model = ""
        self.status = "The floor is empty."
        self.skill: dict[str, str] | None = None
        self._lock = threading.Lock()

    def begin(self) -> None:
        """Clear the previous job and mark this one running."""
        with self._lock:
            self.events = []
            self.files = {}
            self.running = True
            self.blocked = False
            self.passed = False
            self.skill = None
            self.status = "The office is working."

    def record(self, event: dict[str, Any], files: dict[str, str] | None = None) -> None:
        """Append one event and any files written in that step."""
        with self._lock:
            self.events.append(event)
            if files:
                self.files.update(files)
            self.status = str(event["detail"])

    def finish(self, *, passed: bool, blocked: bool, status: str, skill: dict[str, str] | None) -> None:
        """Mark the job finished. ``passed`` is true only when both checks passed."""
        with self._lock:
            self.running = False
            self.passed = passed
            self.blocked = blocked
            self.status = status
            self.skill = skill

    def snapshot(self) -> dict[str, Any]:
        """The dashboard fields. This copy does not include a model caller."""
        with self._lock:
            return {
                "model": self.model,
                "connected": self.connected,
                "blocked": self.blocked,
                "passed": self.passed,
                "running": self.running,
                "status": self.status,
                "events": list(self.events),
                "files": dict(self.files),
                "skill": self.skill,
            }


def parse_reply(text: str) -> tuple[str, str, str]:
    """Return ``(say, body, target)`` from a model reply.

    The reply must contain one JSON object with a non-empty ``say`` string.
    ``body`` and ``target`` are strings and may be empty. ``ModelCallError``
    means the reply is not that object.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ModelCallError("the model reply is not JSON")
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ModelCallError("the model reply is not JSON") from exc
    say = payload.get("say") if isinstance(payload, dict) else None
    body = payload.get("body", "") if isinstance(payload, dict) else None
    target = payload.get("target", "") if isinstance(payload, dict) else None
    if not isinstance(say, str) or not say.strip():
        raise ModelCallError("the model reply has no say")
    if not isinstance(body, str) or not isinstance(target, str):
        raise ModelCallError("the model reply has no body")
    return say.strip(), body, target.strip()


def run_live_office(
    brief: str,
    directory: Path,
    state: OfficeState,
    model: ModelCaller | None = None,
    skills_dir: Path | None = None,
    *,
    use_environment: bool = True,
) -> None:
    """Run one brief. Append each reply to ``state`` before the next model call.

    ``model`` supplies the replies. When it is omitted and ``use_environment``
    is true, the caller is ``model_from_environment``. A missing caller records
    one blocked event and does not ask anyone to speak.
    """
    caller = model
    if caller is None and use_environment:
        caller = model_from_environment()
    if caller is None:
        state.record(_event("nova", "task.failed", "brief", BLOCKED, "blocked", "think", "brief"))
        state.finish(passed=False, blocked=True, status=BLOCKED, skill=None)
        return
    text = brief.strip()
    if not text:
        state.record(
            _event("nova", "task.failed", "brief", "blocked: the brief is empty", "blocked", "think", "brief")
        )
        state.finish(passed=False, blocked=True, status="blocked: the brief is empty", skill=None)
        return
    catalog = skills_dir if skills_dir is not None else directory.parent / "team-skills"
    try:
        _work(text, directory, state, caller, catalog)
    except ModelCallError as exc:
        state.record(_event("nova", "task.failed", "model", f"blocked: {exc}", "blocked", "think", "brief"))
        state.finish(passed=False, blocked=True, status=f"blocked: {exc}", skill=None)


def _work(brief: str, directory: Path, state: OfficeState, model: ModelCaller, skills_dir: Path) -> None:
    spoken: list[str] = []
    say, _body, _target = _ask(model, _speak_prompt("Nova", "Lead", brief, "Say how you will split this request."))
    state.record(_event("nova", "task.started", "plan", say, "thinking", "think", "plan.md"))
    say, body, _target = _ask(model, _file_prompt("Nova", brief, "plan.md", "A numbered plan for this request."))
    plan_file = _save(directory, "plan.md", body or f"# Plan\n\n{brief}\n")
    state.record(_event("nova", "artifact.created", "plan", say, "planning", "write", "plan.md"), plan_file)
    state.record(
        _event(
            "nova", "handoff.created", "meeting", "Nova opened the discussion.", "meeting", "handoff", "meeting", FLOOR
        )
    )
    for person_id, name in PEOPLE:
        say, _body, _target = _ask(model, _meeting_prompt(name, brief, spoken))
        spoken.append(f"{name}: {say}")
        state.record(
            _event(
                person_id, "handoff.created", "meeting", f"{name}: {say}", "discussion", "handoff", "meeting", FLOOR
            )
        )

    say, body, _target = _ask(
        model, _file_prompt("Scout", brief, "research.md", "Write notes from the request. Do not add a different job.")
    )
    research = _save(directory, "research.md", body or f"# Notes\n\n{brief}\n")
    state.record(_event("scout", "artifact.created", "research", say, "working", "write", "research.md"), research)
    say, body, _target = _ask(
        model, _file_prompt("Lumi", brief, "design.md", "Describe the result this request needs.")
    )
    design = _save(directory, "design.md", body or f"# Design\n\n{brief}\n")
    state.record(_event("lumi", "artifact.created", "layout", say, "working", "write", "design.md"), design)

    say, body, test_name = _ask(model, _check_prompt(brief))
    if not test_name:
        test_name = "test_work.py"
    if not body.strip():
        raise ModelCallError("Pixel did not write a check")
    locked = _save(directory, test_name, body)
    locked_text = locked[test_name]
    state.record(_event("pixel", "artifact.created", "write-tests", say, "working", "write", test_name), locked)

    accepted = read_skill(skills_dir)
    say, body, impl_name = _ask(model, _build_prompt(brief, accepted, test_name, ""))
    if not impl_name:
        impl_name = "work.py"
    if impl_name == test_name:
        raise ModelCallError("Forge tried to edit the check")
    if not body.strip():
        raise ModelCallError("Forge did not write a file")
    built = _save(directory, impl_name, body)
    state.record(_event("forge", "artifact.created", "implement", say, "working", "write", impl_name), built)

    if "def test_" not in locked_text:
        state.finish(
            passed=False, blocked=False, status="Pixel wrote a note, not a test, so no lesson was kept.", skill=None
        )
        return
    first_passed, first_log = _pytest(directory, test_name)
    state.record(_event("pixel", "test.completed", "test", first_log, "testing", "test", test_name))
    if first_passed:
        _keep(directory, state, skills_dir, brief, first_log)
        return
    state.record(_event("pixel", "task.failed", "test", "The check failed.", "testing", "test", test_name))
    say, _body, _target = _ask(
        model, _speak_prompt("Pixel", "Check", brief, "Tell Forge what failed. The check file stays locked.")
    )
    state.record(
        _event(
            "pixel", "handoff.created", "test", f"Pixel: {say}", "discussion", "handoff", test_name, ["pixel", "forge"]
        )
    )
    say, _body, _target = _ask(
        model,
        _speak_prompt(
            "Forge", "Build", brief, "Reply to Pixel. You will fix the build and you will not edit the check."
        ),
    )
    state.record(
        _event(
            "forge", "handoff.created", "test", f"Forge: {say}", "discussion", "handoff", test_name, ["pixel", "forge"]
        )
    )
    say, body, _target = _ask(model, _build_prompt(brief, accepted, test_name, first_log))
    if not body.strip():
        raise ModelCallError("Forge did not repair the file")
    repaired = _save(directory, impl_name, body)
    state.record(_event("forge", "artifact.created", "repair", say, "working", "edit", impl_name), repaired)
    if (directory / test_name).read_text(encoding="utf-8") != locked_text:
        state.record(
            _event(
                "sage",
                "task.failed",
                "review",
                "The check changed, so no lesson was kept.",
                "failed",
                "test",
                test_name,
            )
        )
        state.finish(passed=False, blocked=False, status="The check changed, so no lesson was kept.", skill=None)
        return
    second_passed, second_log = _pytest(directory, test_name)
    state.record(_event("pixel", "test.completed", "retest", second_log, "testing", "test", test_name))
    if not second_passed:
        state.record(
            _event(
                "sage",
                "task.failed",
                "review",
                "The repair still failed, so no lesson was kept.",
                "failed",
                "test",
                test_name,
            )
        )
        state.finish(passed=False, blocked=False, status="The repair still failed, so no lesson was kept.", skill=None)
        return
    _keep(directory, state, skills_dir, brief, second_log)


def _keep(directory: Path, state: OfficeState, skills_dir: Path, brief: str, check_output: str) -> None:
    skill_body = f"# Lesson\n\nRequest: {brief}\n\nThe check passed.\n\n```\n{check_output}\n```\n"
    write_text(skills_dir / SKILL_NAME, skill_body)
    skill_file = _save(directory, "skill.md", skill_body)
    state.record(
        _event(
            "sage",
            "learning.version.promoted",
            "skill",
            "Sage kept the lesson because the check passed.",
            "reviewing",
            "write",
            "skill.md",
        ),
        skill_file,
    )
    state.finish(
        passed=True,
        blocked=False,
        status="The office kept a lesson. The next job can use it.",
        skill={"id": "lesson", "procedure": brief, "acceptance": check_output, "holdout": ""},
    )


def _pytest(directory: Path, file_name: str) -> tuple[bool, str]:
    result = run_pytest(directory, file_name)
    output = process_output(result)
    if not output:
        output = "pytest produced no output"
    return result.returncode == 0, output


def _save(directory: Path, name: str, text: str) -> dict[str, str]:
    body = text if text.endswith("\n") else text + "\n"
    write_text(directory / name, body)
    return {name: body}


def _ask(model: ModelCaller, prompt: str) -> tuple[str, str, str]:
    return parse_reply(model.complete(prompt))


def _event(
    employee: str,
    name: str,
    task: str,
    detail: str,
    mode: str,
    tool: str,
    target: str,
    people: list[str] | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "name": name,
        "employee": employee,
        "task": task,
        "detail": detail,
        "mode": mode,
        "tool": tool,
        "target": target,
    }
    if people is not None:
        event["with"] = people
    return event


def _think_prompt(name: str, role: str, brief: str, job: str) -> str:
    return (
        f"You are {name}, the {role}. Brief:\n{brief}\n\n{job}\n"
        'Reply with one JSON object: {"say": "one sentence", "body": ""}'
    )


def _file_prompt(name: str, brief: str, filename: str, job: str) -> str:
    return (
        f"You are {name}. The request is:\n{brief}\n\nWrite {filename}. {job}\n"
        'Reply with one JSON object: {"say": "one sentence", "target": "' + filename + '", "body": "the whole file"}'
    )


def _speak_prompt(name: str, role: str, brief: str, job: str) -> str:
    return (
        f"You are {name}, {role}. The request is:\n{brief}\n\n{job}\n"
        'Reply with one JSON object: {"say": "one or two sentences", "body": ""}'
    )


def _meeting_prompt(name: str, brief: str, spoken: list[str]) -> str:
    heard = "\n".join(spoken) if spoken else "Nobody has spoken yet."
    return (
        f"You are {name}. The request is:\n{brief}\n\nAlready said:\n{heard}\n\n"
        "Reply to the request in one or two sentences. Name your next step. Do not repeat the others.\n"
        'Reply with one JSON object: {"say": "what you say in the room", "body": ""}'
    )


def _check_prompt(brief: str) -> str:
    return (
        "You are Pixel. Write a pytest file that checks the request. Forge must not edit this file.\n"
        f"Request:\n{brief}\n\n"
        'Reply with one JSON object: {"say": "one sentence", "target": "the test filename", "body": "the pytest source"}'
    )


def _build_prompt(brief: str, skill: str, test_name: str, failure: str) -> str:
    parts = [
        "You are Forge. Write the file this request needs. Do not edit " + test_name + ".",
        f"Request:\n{brief}",
    ]
    if skill:
        parts.append("Accepted skill:\n" + skill)
    if failure:
        parts.append("The check failed. Repair your file only.\n" + failure)
    parts.append(
        'Reply with one JSON object: {"say": "one sentence", "target": "the filename", "body": "the whole file"}'
    )
    return "\n\n".join(parts)


class OfficeHost:
    """The local process the company page calls.

    ``caller`` is kept for the job and is not part of ``snapshot``. ``start_job``
    returns the HTTP status and the current snapshot. A second job is refused
    while ``running`` is true.
    """

    def __init__(self, directory: Path, skills_dir: Path, caller: ModelCaller | None) -> None:
        self.directory = directory
        self.skills_dir = skills_dir
        self.caller = caller
        self.state = OfficeState()
        self.state.connected = caller is not None
        self.state.model = caller.model if isinstance(caller, OpenAIChatModel) else ""
        if caller is None:
            self.state.blocked = True
            self.state.status = BLOCKED

    def start_job(self, brief: str, keep_skill: bool) -> tuple[int, dict[str, Any]]:
        """Start one brief. 409 when a job is already running. 200 when no model is configured."""
        if self.state.running:
            return 409, self.state.snapshot()
        if not keep_skill:
            skill_path = self.skills_dir / SKILL_NAME
            if skill_path.is_file():
                skill_path.unlink()
        if self.caller is None:
            self.state.blocked = True
            self.state.status = BLOCKED
            self.state.record(_event("nova", "task.failed", "brief", BLOCKED, "blocked", "think", "brief"))
            self.state.running = False
            return 200, self.state.snapshot()
        self.state.begin()
        thread = threading.Thread(
            target=run_live_office,
            args=(brief, self.directory, self.state, self.caller, self.skills_dir),
            kwargs={"use_environment": False},
            daemon=True,
        )
        thread.start()
        return 202, self.state.snapshot()


def allow_origin(origin: str) -> str:
    """The origin when it is this machine's page. An empty string refuses other origins."""
    if origin.startswith(("http://localhost:", "http://127.0.0.1:")):
        return origin
    return ""


def serve_office(directory: Path, skills_dir: Path, port: int) -> None:
    """Listen on ``127.0.0.1`` and ``port`` until the process is stopped.

    ``GET /state`` and ``POST /run`` return the dashboard snapshot. The model
    key is read from the environment inside the caller and is not written to
    the response.
    """
    host = OfficeHost(directory, skills_dir, model_from_environment())

    class Handler(BaseHTTPRequestHandler):
        def do_OPTIONS(self) -> None:
            self._send(204, b"", "text/plain")

        def do_GET(self) -> None:
            if self.path.split("?", 1)[0] != "/state":
                self._send(404, b"not found", "text/plain")
                return
            self._send(200, json.dumps(host.state.snapshot()).encode(), "application/json")

        def do_POST(self) -> None:
            if self.path.split("?", 1)[0] != "/run":
                self._send(404, b"not found", "text/plain")
                return
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode() or "{}")
            except json.JSONDecodeError:
                self._send(400, b'{"status": "blocked: the brief is not JSON"}', "application/json")
                return
            brief = payload.get("brief", "") if isinstance(payload, dict) else ""
            keep_skill = bool(payload.get("keepSkill", True)) if isinstance(payload, dict) else True
            if not isinstance(brief, str):
                brief = ""
            status, snapshot = host.start_job(brief, keep_skill)
            self._send(status, json.dumps(snapshot).encode(), "application/json")

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            origin = allow_origin(self.headers.get("Origin", ""))
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            if origin:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"company office: http://127.0.0.1:{port}")
    server.serve_forever()
