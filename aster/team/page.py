"""The team workspace page. It shows the recorded events, not a live invention.

The page reads ``events.jsonl`` from the run directory. Each specialist shows
the state of that specialist's latest event. Replay walks those same events.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from aster.team.run import SOFTWARE_TEAM, load_events


def workspace_page(directory: Path) -> str:
    """The HTML page for the team run in ``directory``."""
    events = list(load_events(directory))
    review = directory / "review.md"
    skill = directory / "skill.md"
    files = sorted(path.name for path in directory.iterdir() if path.is_file()) if directory.is_dir() else []
    payload = json.dumps(
        {
            "team": [member.__dict__ for member in SOFTWARE_TEAM],
            "events": events,
            "review": review.read_text(encoding="utf-8") if review.is_file() else "",
            "skill": skill.read_text(encoding="utf-8") if skill.is_file() else "",
            "files": files,
        }
    )
    return _PAGE.replace("/*RUN*/", payload)


def latest_state(events: Sequence[Mapping[str, str]], role_id: str) -> str:
    """The visual state of ``role_id`` after ``events``.

    The state is idle until that specialist has an event. ``testing`` is only
    the latest ``test.completed`` event. ``blocked`` is a failed task whose
    detail says blocked. A later completed task is ``done``.
    """
    state = "idle"
    for event in events:
        if event.get("role_id") != role_id:
            continue
        name = event.get("name", "")
        detail = event.get("detail", "")
        if name == "task.failed" and "blocked" in detail.lower():
            state = "blocked"
        elif name == "task.failed":
            state = "failed"
        elif name == "test.completed":
            state = "testing"
        elif name == "task.started":
            state = "working"
        elif name == "task.completed" and "failed" not in detail.lower():
            state = "done"
    return state


_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Aster team</title>
<style>
body{margin:0;background:#0c1016;color:#e7eef8;font:15px/1.5 Georgia,serif}
header{padding:20px 28px;border-bottom:1px solid #243044}
h1{margin:0;font-size:22px;letter-spacing:.14em}
main{display:grid;grid-template-columns:1.2fr .8fr;gap:20px;padding:20px 28px}
.room{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.card{background:#141b26;border:1px solid #2a3a52;border-radius:12px;padding:14px;min-height:140px}
.name{font-weight:700;letter-spacing:.08em}
.role{color:#8eb6e8;font-size:13px}
.figure{height:54px;margin:10px 0;border-radius:27px 27px 8px 8px;background:#1d4e89}
.working .figure{animation:pulse 1.2s ease-in-out infinite}
.done .figure{background:#2f6b4f}
.failed .figure{background:#8a3b32}
.blocked .figure{background:#8a3b32;outline:3px solid #e6c084}
.testing .figure{background:#8eb6e8}
.state{font-size:13px;color:#c5d4ea}
pre{white-space:pre-wrap;background:#10161f;padding:12px;border-radius:8px;font:12px/1.4 ui-monospace,monospace}
button{background:#1d4e89;color:#fff;border:0;border-radius:8px;padding:8px 12px;cursor:pointer}
@keyframes pulse{50%{transform:translateY(-4px)}}
</style>
</head>
<body>
<header><h1>ASTER TEAM</h1><p>The characters show the recorded run. Replay does not run the work again.</p></header>
<main>
<section class="room" id="room"></section>
<section>
<button id="replay" type="button">Replay recorded events</button>
<pre id="log"></pre>
</section>
</main>
<script>
const run = /*RUN*/;
const room = document.getElementById("room");
const log = document.getElementById("log");
function stateFor(events, role){
  let state = "idle";
  for (const event of events){
    if (event.role_id !== role) continue;
    if (event.name === "task.failed" && /blocked/i.test(event.detail)) state = "blocked";
    else if (event.name === "task.failed") state = "failed";
    else if (event.name === "test.completed") state = "testing";
    else if (event.name === "task.started") state = "working";
    else if (event.name === "task.completed" && !/failed/i.test(event.detail)) state = "done";
  }
  return state;
}
function draw(events){
  room.innerHTML = "";
  for (const member of run.team){
    const state = stateFor(events, member.role_id);
    const latest = [...events].reverse().find(event => event.role_id === member.role_id);
    const card = document.createElement("article");
    card.className = "card " + state;
    card.innerHTML = '<div class="name"></div><div class="role"></div><div class="figure"></div><div class="state"></div>';
    card.querySelector(".name").textContent = member.name;
    card.querySelector(".role").textContent = member.title;
    card.querySelector(".state").textContent = latest ? latest.detail.split("\\n")[0] : "Idle";
    room.appendChild(card);
  }
  log.textContent = [
    "Files: " + run.files.join(", "),
    events.map(event => event.role_id + " " + event.name + " — " + event.detail.split("\\n")[0]).join("\\n"),
    run.skill,
    run.review
  ].filter(Boolean).join("\\n\\n");
}
draw(run.events);
document.getElementById("replay").onclick = () => {
  let index = 0;
  const timer = setInterval(() => {
    index += 1;
    draw(run.events.slice(0, index));
    if (index >= run.events.length) clearInterval(timer);
  }, 400);
};
</script>
</body>
</html>
"""
