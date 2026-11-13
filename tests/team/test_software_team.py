"""The software team asks the model for booking.py, keeps Pixel's tests, and learns only after the holdout passes."""

from aster.team.model import ModelCaller
from aster.team.page import latest_state, workspace_page
from aster.team.run import acceptance_test, holdout_test, load_events, rollback_skill, run_software_team

BRIEF = "Build a booking website for my photography business. Prevent double booking."
BUGGY = """class Bookings:
    def book(self, slot: str) -> bool:
        return True
"""
FIXED = """class Bookings:
    def __init__(self) -> None:
        self.taken: set[str] = set()

    def book(self, slot: str) -> bool:
        if slot in self.taken:
            return False
        self.taken.add(slot)
        return True
"""


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


def test_a_booking_brief_fails_once_then_the_holdout_accepts_the_skill(tmp_path):
    model = ScriptedModel([BUGGY, FIXED])
    skills = tmp_path / "skills"
    studio = tmp_path / "studio"
    run = run_software_team(BRIEF, studio, model, skills, use_environment=False)

    assert run.passed and not run.blocked
    assert (studio / "test_booking.py").read_text() == acceptance_test()
    assert (studio / "holdout_booking.py").read_text() == holdout_test()
    assert "test_a_second_slot_stays_free" not in model.prompts[1]
    assert holdout_test() not in model.prompts[1]
    assert "class Bookings" in (studio / "booking.py").read_text()
    bookings = _load_bookings(studio)
    assert bookings.book("2026-11-10T10:00") is True
    assert bookings.book("2026-11-10T10:00") is False
    events = list(load_events(studio))
    failed_at = next(index for index, event in enumerate(events) if event["name"] == "task.failed")
    retest = next(
        event for event in events[failed_at:] if event["task_id"] == "retest" and event["name"] == "test.completed"
    )
    assert "exited 0" in retest["detail"]
    skill = (skills / "refuse-duplicate.md").read_text()
    assert "Bookings.book returns false" in skill
    assert "passed" in skill
    assert any(event["name"] == "learning.version.promoted" for event in events)
    testing_events = events[: events.index(retest) + 1]
    assert latest_state(testing_events, "pixel") == "testing"
    assert latest_state(events, "pixel") == "done"
    page = workspace_page(studio)
    assert "Nova" in page and "booking.py" in page and "Refuse a duplicate booking" in page

    again = ScriptedModel([FIXED])
    second = run_software_team(BRIEF, tmp_path / "next", again, skills, use_environment=False)
    assert "Accepted skill" in again.prompts[0]
    assert second.passed
    assert rollback_skill(skills)
    assert not (skills / "refuse-duplicate.md").exists()


def test_a_missing_model_blocks_forge_and_writes_no_application(tmp_path):
    run = run_software_team(BRIEF, tmp_path / "studio", use_environment=False)

    assert run.blocked and not run.passed
    assert not (tmp_path / "studio" / "booking.py").exists()
    assert latest_state(load_events(tmp_path / "studio"), "forge") == "blocked"
    assert "No application was built" in workspace_page(tmp_path / "studio")


def _load_bookings(directory):
    import importlib.util

    spec = importlib.util.spec_from_file_location("team_booking", directory / "booking.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Bookings()
