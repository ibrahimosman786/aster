"""The ``aster team`` command: run a software team, or open its recorded workspace."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from aster.team.office_live import serve_office
from aster.team.page import workspace_page
from aster.team.run import rollback_skill, run_software_team


def load_local_env() -> None:
    """Fill unset provider variables from ``.env`` in the current directory."""
    if not Path(".env").is_file():
        return
    from dotenv import load_dotenv

    load_dotenv(Path(".env"), override=False)


def main(argv: list[str]) -> int:
    """Run ``argv`` as ``aster team``. Returns the process status."""
    load_local_env()
    parser = argparse.ArgumentParser(prog="aster team")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run the software team on one brief.")
    run.add_argument("brief", help="The work the team should do.")
    run.add_argument(
        "--out", type=Path, required=True, help="The directory that receives the project and the event log."
    )
    run.add_argument(
        "--skills", type=Path, default=Path(".aster/team-skills"), help="Where an accepted skill is stored."
    )
    rollback = commands.add_parser("rollback", help="Remove the accepted skill so the next run does not use it.")
    rollback.add_argument("--skills", type=Path, default=Path(".aster/team-skills"), help="The skill directory.")
    serve = commands.add_parser("serve", help="Show a recorded team run in the browser.")
    serve.add_argument("--run", type=Path, required=True, help="The directory written by aster team run.")
    serve.add_argument("--port", type=int, default=8910, help="The port of the workspace page.")
    args = parser.parse_args(argv)
    if args.command == "rollback":
        removed = rollback_skill(args.skills)
        print("removed" if removed else "absent")
        return 0
    if args.command == "run":
        result = run_software_team(args.brief, args.out, skills_dir=args.skills)
        print(f"team run: {result.directory}")
        if result.blocked:
            print("blocked")
            return 1
        print("passed" if result.passed else "failed")
        return 0 if result.passed else 1
    page = workspace_page(args.run)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = page.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"team workspace: http://127.0.0.1:{args.port}")
    server.serve_forever()
    return 0


def company_main(argv: list[str]) -> int:
    """Run ``argv`` as ``aster company``. Returns the process status."""
    load_local_env()
    parser = argparse.ArgumentParser(prog="aster company")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Run the live office for the company page.")
    serve.add_argument("--port", type=int, default=8911, help="The port of the live office.")
    serve.add_argument("--out", type=Path, default=Path(".aster/company-run"), help="Where the office writes files.")
    serve.add_argument(
        "--skills", type=Path, default=Path(".aster/team-skills"), help="Where an accepted skill is stored."
    )
    args = parser.parse_args(argv)
    if args.command == "serve":
        serve_office(args.out, args.skills, args.port)
        return 0
    return 2
