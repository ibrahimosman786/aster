"""The live office asks the model to speak and keeps a skill only after both checks."""

import json

from aster.team.model import ModelCaller, OpenAIChatModel
from aster.team.office_live import BLOCKED, OfficeHost, OfficeState, run_live_office

BRIEF = "Build a booking website for my photography business. Prevent double booking."
BUGGY = "class Bookings:\n    def book(self, slot: str) -> bool:\n        return True\n"
FIXED = (
    "class Bookings:\n"
    "    def __init__(self) -> None:\n"
    "        self.taken: set[str] = set()\n\n"
    "    def book(self, slot: str) -> bool:\n"
    "        if slot in self.taken:\n"
    "            return False\n"
    "        self.taken.add(slot)\n"
    "        return True\n"
)


def reply(say: str, body: str = "", target: str = "") -> str:
    return json.dumps({"say": say, "body": body, "target": target})


class ScriptedModel(ModelCaller):
    """A stand-in that returns the next prepared reply and keeps every prompt."""

    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.replies:
            raise RuntimeError("no reply")
        return self.replies.pop(0)


def meeting_replies() -> list[str]:
    return [reply(f"{name} will take the next step.") for name in ("Nova", "Scout", "Lumi", "Pixel", "Forge", "Sage")]


CHECK = '''"""Pixel's check. Forge does not edit this file."""

from booking import Bookings


def test_a_slot_cannot_be_booked_twice():
    bookings = Bookings()
    assert bookings.book("2026-11-10T10:00") is True
    assert bookings.book("2026-11-10T10:00") is False
'''


def opening(booking: str) -> list[str]:
    return [
        reply("I will split the request."),
        reply("The plan is ready.", "# Plan\n\nBook each slot once.\n", "plan.md"),
        *meeting_replies(),
        reply("I wrote notes from the request.", "# Notes\n\nBook each slot once.\n", "research.md"),
        reply("One booking screen.", "# Design\n\nOne screen.\n", "design.md"),
        reply("I locked the check.", CHECK, "test_booking.py"),
        reply("The first desk is written.", booking, "booking.py"),
    ]


def test_a_failed_check_is_repaired_once_and_the_skill_follows_the_holdout(tmp_path):
    model = ScriptedModel(
        [
            *opening(BUGGY),
            reply("The check failed. The tests stay locked."),
            reply("I will not edit the tests."),
            reply("The desk now refuses a duplicate.", FIXED),
        ]
    )
    state = OfficeState()
    skills = tmp_path / "skills"
    run_live_office(BRIEF, tmp_path / "office", state, model, skills, use_environment=False)

    assert state.passed and not state.blocked
    failed_at = next(index for index, event in enumerate(state.events) if event["name"] == "task.failed")
    edit_at = next(
        index
        for index, event in enumerate(state.events)
        if event["tool"] == "edit" and event["target"] == "booking.py"
    )
    assert edit_at > failed_at
    assert sum(1 for event in state.events if event["tool"] == "edit") == 1
    repair = next(prompt for prompt in model.prompts if "Repair your file only." in prompt)
    assert "Do not edit test_booking.py" in repair
    assert any(event["name"] == "learning.version.promoted" for event in state.events)
    assert "Nova will take the next step." in " ".join(event["detail"] for event in state.events)
    assert (skills / "refuse-duplicate.md").is_file()
    assert state.skill is not None

    again = ScriptedModel([*opening(FIXED)])
    second = OfficeState()
    run_live_office("Build a booking website.", tmp_path / "next", second, again, skills, use_environment=False)
    assert second.passed
    assert not any(event["tool"] == "edit" for event in second.events)
    assert any("Accepted skill" in prompt for prompt in again.prompts)


def test_a_missing_model_blocks_without_a_meeting(tmp_path):
    state = OfficeState()
    run_live_office(BRIEF, tmp_path / "office", state, use_environment=False)

    assert state.blocked and not state.passed
    assert state.events == [
        {
            "name": "task.failed",
            "employee": "nova",
            "task": "brief",
            "detail": BLOCKED,
            "mode": "blocked",
            "tool": "think",
            "target": "brief",
        }
    ]
    assert not any(event["mode"] in {"meeting", "discussion"} for event in state.events)


def test_the_dashboard_snapshot_does_not_contain_the_api_key(tmp_path):
    host = OfficeHost(
        tmp_path / "office",
        tmp_path / "skills",
        OpenAIChatModel("https://api.deepseek.com", "sk-secret-test", "deepseek-chat"),
    )
    body = json.dumps(host.state.snapshot())

    assert host.state.connected
    assert host.state.model == "deepseek-chat"
    assert "sk-secret-test" not in body
    assert "api_key" not in body


def test_a_request_that_is_not_booking_does_not_write_booking_py(tmp_path):
    note = "def test_the_note_mentions_tea():\n    assert 'tea' in open('note.md').read()\n"
    model = ScriptedModel(
        [
            reply("I will plan a note about tea."),
            reply("The plan is a note.", "# Plan\n\nWrite about tea.\n", "plan.md"),
            *meeting_replies(),
            reply("The request is a note about tea.", "# Notes\n\nTea.\n", "research.md"),
            reply("A single page.", "# Design\n\nOne page about tea.\n", "design.md"),
            reply("The check looks for the word tea.", note, "test_note.py"),
            reply("I wrote the note.", "A short note about tea.\n", "note.md"),
        ]
    )
    state = OfficeState()
    run_live_office(
        "Write a one-page note about tea.",
        tmp_path / "office",
        state,
        model,
        tmp_path / "skills",
        use_environment=False,
    )

    assert state.passed
    assert not any(event["target"] == "booking.py" for event in state.events)
    assert "tea" in (tmp_path / "office" / "note.md").read_text()
