"""Run one software team on a brief and keep the recorded result.

A ``TeamRun`` is one directory. Nova, Scout, and Lumi write the brief down.
Pixel writes the acceptance test and a separate holdout fixture. Forge may
write only ``booking.py``, and only with text returned by the model. Pixel
runs the acceptance test. A failure is sent back to Forge once. The skill is
written only when that repair passes and the holdout fixture, which Forge is
not shown, also passes.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from aster.team.model import ModelCallError, ModelCaller, model_from_environment

SKILL_NAME = "refuse-duplicate.md"
ACCEPTANCE_TEST = "test_booking.py"
HOLDOUT_TEST = "holdout_booking.py"
APPLICATION = "booking.py"


@dataclass(frozen=True)
class Specialist:
    """One member of the software team.

    ``role_id`` is the stable name used in events. ``name`` is the character
    name. ``title`` is the job. ``responsibility`` is the work that member does
    on a run.
    """

    role_id: str
    name: str
    title: str
    responsibility: str


SOFTWARE_TEAM: tuple[Specialist, ...] = (
    Specialist("nova", "Nova", "Team lead", "Turns the brief into acceptance checks."),
    Specialist("scout", "Scout", "Researcher", "Records the requirements the brief actually states."),
    Specialist("lumi", "Lumi", "Designer", "Writes the screens the brief needs."),
    Specialist("forge", "Forge", "Developer", "Writes booking.py from the model, then repairs it once."),
    Specialist("pixel", "Pixel", "Tester", "Writes the tests and runs pytest."),
    Specialist("sage", "Sage", "Reviewer", "Quotes the pytest output in the review."),
)


@dataclass(frozen=True)
class TeamEvent:
    """One recorded action.

    ``name`` is the event name. ``role_id`` is the specialist. ``task_id`` is
    the task. ``detail`` is the short result a person can read. ``created_at``
    is the UTC timestamp.
    """

    name: str
    role_id: str
    task_id: str
    detail: str
    created_at: str


@dataclass
class TeamRun:
    """The recorded result of one brief.

    ``directory`` is the project directory. ``events`` is the ordered log.
    ``passed`` is true only when the repaired application passes the acceptance
    test and the holdout fixture. ``blocked`` is true when Forge did not receive
    model text. ``pytest_output`` is the last acceptance-test output.
    """

    brief: str
    directory: Path
    events: list[TeamEvent] = field(default_factory=list)
    passed: bool = False
    blocked: bool = False
    pytest_output: str = ""

    def event(self, name: str, role_id: str, task_id: str, detail: str) -> None:
        """Append one event and write the log again."""
        self.events.append(
            TeamEvent(
                name=name,
                role_id=role_id,
                task_id=task_id,
                detail=detail,
                created_at=datetime.now(UTC).isoformat(),
            )
        )
        lines = [json.dumps(event.__dict__, ensure_ascii=False) for event in self.events]
        (self.directory / "events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_software_team(
    brief: str,
    directory: Path,
    model: ModelCaller | None = None,
    skills_dir: Path | None = None,
    *,
    use_environment: bool = True,
) -> TeamRun:
    """Run the software team on ``brief`` inside ``directory``.

    ``model`` writes ``booking.py``. When ``model`` is omitted and
    ``use_environment`` is true, the caller is the configured provider. When no
    caller is available, or a call fails, Forge is blocked and ``booking.py``
    is not invented. ``skills_dir`` is where an accepted skill is stored for a
    later run. ``ValueError`` when the brief is empty.
    """
    text = brief.strip()
    if not text:
        raise ValueError("a team run needs a brief")
    directory.mkdir(parents=True, exist_ok=True)
    catalog = skills_dir if skills_dir is not None else directory.parent / "team-skills"
    caller = model if model is not None else model_from_environment() if use_environment else None
    run = TeamRun(brief=text, directory=directory)
    write_project_notes(run, text)
    write_tests(run)
    protected = {name: file_hash(directory / name) for name in (ACCEPTANCE_TEST, HOLDOUT_TEST)}
    skill = read_skill(catalog)
    if caller is None:
        block(run, "implement", "blocked: set ASTER_UPSTREAM_URL and ASTER_UPSTREAM_API_KEY")
        write_review(run, "Forge was blocked. No application was built.")
        return run
    if not write_application(run, caller, skill, "implement", failure=""):
        write_review(run, "Forge was blocked. No application was built.")
        return run
    if protected_changed(directory, protected):
        block(run, "implement", "blocked: the acceptance test changed")
        return run
    first = run_pytest(directory, ACCEPTANCE_TEST)
    record_test(run, "test", "First acceptance run", first)
    if first.returncode == 0:
        return finish_after_acceptance(run, catalog, protected, first, repaired=False)
    handoff(run, "pixel", "forge", "test", ACCEPTANCE_TEST)
    failure = process_output(first)
    if not write_application(run, caller, skill, "repair", failure=failure):
        write_review(run, f"The repair was blocked.\n\n```\n{failure}\n```\n")
        return run
    if protected_changed(directory, protected):
        block(run, "repair", "blocked: the acceptance test changed")
        return run
    second = run_pytest(directory, ACCEPTANCE_TEST)
    record_test(run, "retest", "Second acceptance run", second)
    return finish_after_acceptance(run, catalog, protected, second, repaired=True)


def rollback_skill(skills_dir: Path) -> bool:
    """Remove the accepted duplicate-booking skill. True when a file was removed."""
    path = skills_dir / SKILL_NAME
    if not path.is_file():
        return False
    path.unlink()
    return True


def read_skill(skills_dir: Path) -> str:
    """The accepted skill text, or an empty string when none is stored."""
    path = skills_dir / SKILL_NAME
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def load_events(directory: Path) -> Sequence[Mapping[str, str]]:
    """The events written in ``directory`` / ``events.jsonl``, in order."""
    path = directory / "events.jsonl"
    if not path.is_file():
        return ()
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_project_notes(run: TeamRun, brief: str) -> None:
    """Nova, Scout, and Lumi write the brief down. They do not invent sources."""
    write_text(run.directory / "requirements.md", f"# Requirements\n\n{brief}\n\n- A slot can be booked once.\n")
    run.event("task.started", "nova", "requirements", "Nova wrote the acceptance checks from the brief.")
    run.event("artifact.created", "nova", "requirements", "requirements.md")
    run.event("task.completed", "nova", "requirements", "requirements.md requires a slot to be booked once.")
    handoff(run, "nova", "scout", "requirements", "requirements.md")
    lines = [line.strip() for line in brief.splitlines() if line.strip()]
    body = "\n".join(f"- {line}" for line in lines)
    research = f"# Research\n\nThese lines are copied from the brief. They are not outside sources.\n\n{body}\n"
    write_text(run.directory / "research.md", research)
    run.event("task.started", "scout", "research", "Scout listed only the requirements stated in the brief.")
    run.event("artifact.created", "scout", "research", "research.md")
    run.event("task.completed", "scout", "research", "research.md has no unsupported claims.")
    handoff(run, "scout", "lumi", "research", "research.md")
    layout = (
        "# Layout\n\n"
        "One screen lists open slots. One action books a slot. "
        "A second attempt on the same slot is refused.\n\n"
        f"Brief: {brief}\n"
    )
    write_text(run.directory / "layout.md", layout)
    run.event("task.started", "lumi", "layout", "Lumi described the screens the brief needs.")
    run.event("artifact.created", "lumi", "layout", "layout.md")
    run.event("task.completed", "lumi", "layout", "layout.md names the screens. It is not a rendered page.")
    handoff(run, "lumi", "forge", "layout", "layout.md")


def write_tests(run: TeamRun) -> None:
    """Pixel writes the acceptance test and the holdout fixture before Forge repairs anything."""
    write_text(run.directory / ACCEPTANCE_TEST, acceptance_test())
    write_text(run.directory / HOLDOUT_TEST, holdout_test())
    run.event("task.started", "pixel", "write-tests", "Pixel wrote the acceptance test and the holdout fixture.")
    run.event("artifact.created", "pixel", "write-tests", ACCEPTANCE_TEST)
    run.event("artifact.created", "pixel", "write-tests", HOLDOUT_TEST)
    run.event("task.completed", "pixel", "write-tests", "Forge is not allowed to edit either test.")
    handoff(run, "pixel", "forge", "write-tests", ACCEPTANCE_TEST)


def write_application(run: TeamRun, model: ModelCaller, skill: str, task_id: str, failure: str) -> bool:
    """Ask the model for ``booking.py``. False when the call is blocked."""
    run.event("task.started", "forge", task_id, f"Forge asked the model for {APPLICATION}.")
    prompt = application_prompt(run, skill, failure)
    try:
        reply = model.complete(prompt)
        source = python_from_model(reply)
    except ModelCallError as exc:
        block(run, task_id, f"blocked: {exc}")
        return False
    write_text(run.directory / APPLICATION, source)
    run.event("artifact.created", "forge", task_id, APPLICATION)
    run.event("task.completed", "forge", task_id, f"{APPLICATION} was written from the model reply.")
    return True


def finish_after_acceptance(
    run: TeamRun,
    skills_dir: Path,
    protected: Mapping[str, str],
    acceptance: subprocess.CompletedProcess[str],
    *,
    repaired: bool,
) -> TeamRun:
    """Run the holdout fixture and, after a passing repair, store the skill."""
    output = process_output(acceptance)
    run.pytest_output = output
    passed = acceptance.returncode == 0 and not protected_changed(run.directory, protected)
    holdout_output = ""
    if passed:
        holdout = run_pytest(run.directory, HOLDOUT_TEST)
        holdout_output = process_output(holdout)
        record_test(run, "holdout", "Holdout fixture", holdout)
        passed = holdout.returncode == 0
    run.passed = passed
    if repaired and passed:
        skill = skill_text(output, holdout_output)
        skills_dir.mkdir(parents=True, exist_ok=True)
        write_text(skills_dir / SKILL_NAME, skill)
        write_text(run.directory / "skill.md", skill)
        run.event("learning.version.promoted", "sage", "skill", skill)
        run.event("artifact.created", "sage", "skill", "skill.md")
    review = review_text(run.brief, output, passed)
    write_text(run.directory / "review.md", review)
    run.event("task.completed" if passed else "task.failed", "sage", "review", review.splitlines()[0])
    return run


def block(run: TeamRun, task_id: str, detail: str) -> None:
    """Record Forge as blocked and stop the claim that an application exists."""
    run.blocked = True
    run.event("task.failed", "forge", task_id, detail)


def record_test(run: TeamRun, task_id: str, label: str, result: subprocess.CompletedProcess[str]) -> None:
    """Record one pytest run. A non-zero exit is a failed task."""
    output = process_output(result)
    run.event("test.completed", "pixel", task_id, f"{label} exited {result.returncode}.\n{output}")
    if result.returncode == 0:
        run.event("task.completed", "pixel", task_id, f"{label} passed.")
    else:
        run.event("task.failed", "pixel", task_id, f"{label} failed.")


def handoff(run: TeamRun, source: str, target: str, task_id: str, artifact: str) -> None:
    run.event("handoff.created", source, task_id, f"{source} handed {artifact} to {target}.")


def write_review(run: TeamRun, verdict: str) -> None:
    review = f"# Review\n\n{verdict}\n\nBrief: {run.brief}\n"
    write_text(run.directory / "review.md", review)
    run.event("task.failed", "sage", "review", verdict.splitlines()[0])


def application_prompt(run: TeamRun, skill: str, failure: str) -> str:
    """The prompt Forge sends. It does not include the holdout fixture."""
    requirements = (run.directory / "requirements.md").read_text(encoding="utf-8")
    layout = (run.directory / "layout.md").read_text(encoding="utf-8")
    parts = [
        "Write Python for booking.py only.",
        "Define class Bookings with book(self, slot: str) -> bool.",
        "Return only the Python source.",
        "Do not write tests.",
        requirements,
        layout,
    ]
    if skill:
        parts.append("Accepted skill:\n" + skill)
    if failure:
        parts.append("The acceptance test failed. Repair booking.py only.\n" + failure)
    return "\n\n".join(parts)


def python_from_model(text: str) -> str:
    """The Python source in a model reply. ``ModelCallError`` when it has no Bookings class."""
    fenced = re.findall(r"```(?:python)?\s*\n(.*?)```", text, flags=re.DOTALL)
    source = fenced[0] if fenced else text
    if "class Bookings" not in source:
        raise ModelCallError("the model did not return a Bookings class")
    return source.strip() + "\n"


def acceptance_test() -> str:
    return '''"""Pixel's acceptance test. Forge does not edit this file."""

from booking import Bookings


def test_a_slot_cannot_be_booked_twice():
    bookings = Bookings()
    assert bookings.book("2026-11-10T10:00") is True
    assert bookings.book("2026-11-10T10:00") is False
'''


def holdout_test() -> str:
    return '''"""A separate fixture. It is not shown to Forge."""

from booking import Bookings


def test_a_second_slot_stays_free():
    bookings = Bookings()
    assert bookings.book("morning") is True
    assert bookings.book("afternoon") is True
    assert bookings.book("morning") is False
'''


def skill_text(acceptance_output: str, holdout_output: str) -> str:
    return (
        "# Refuse a duplicate booking\n\n"
        "Procedure: Bookings.book returns false when the slot was already booked.\n\n"
        f"Acceptance pytest:\n```\n{acceptance_output}\n```\n\n"
        f"Holdout pytest:\n```\n{holdout_output}\n```\n"
    )


def review_text(brief: str, pytest_output: str, passed: bool) -> str:
    verdict = "The work passed the recorded tests." if passed else "The work failed the recorded tests."
    return f"# Review\n\n{verdict}\n\nBrief: {brief}\n\n```\n{pytest_output}\n```\n"


def run_pytest(directory: Path, file_name: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", file_name, "-q"],
        cwd=directory,
        capture_output=True,
        text=True,
        check=False,
    )


def process_output(result: subprocess.CompletedProcess[str]) -> str:
    return f"{result.stdout}\n{result.stderr}".strip()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected_changed(directory: Path, protected: Mapping[str, str]) -> bool:
    return any(file_hash(directory / name) != digest for name, digest in protected.items())
