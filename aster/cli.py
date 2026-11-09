"""aster CLI: entry point for aster.

Usage:
  aster serve --inference.upstream-url URL --inference.upstream-model MODEL  # connect a provider
  aster serve -c path/to/stack.yaml             # start a configured stack

`aster serve` starts local inference or a provider deployment without YAML, or reads
a config's components and assembles their processes. Run `aster serve --help` for
config options; the configuration reference documents the layout.

Named recipe YAML is deployment data, not library data: point
``ASTER_RECIPE_CONFIG_DIR`` at your own directory.
"""

from __future__ import annotations

import sys

_COMMANDS = {"serve", "check-artifacts"}


def _help_text():
    return """\
usage: aster <command> [options]

  serve            Start inference, connect a provider, or run a configured stack
  check-artifacts  Check that each commit history resolves to stored files, before an upgrade

  -c CONFIG   Optional config file; omitted means configuration-free startup
  --version   Print the installed aster version

Examples:
  aster serve --inference.upstream-url http://localhost:8000 --inference.upstream-model my-model
  aster serve -c path/to/local-sglang.yaml
  aster serve -c path/to/external-provider.yaml
"""


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)

    if not argv:
        print(_help_text(), file=sys.stderr)
        sys.exit(2)

    if argv[0] in ("-h", "--help"):
        print(_help_text())
        sys.exit(0)

    if argv[0] in ("-V", "--version"):
        from aster.core.version import __version__

        print(f"aster {__version__}")
        sys.exit(0)

    cmd = argv[0]
    rest = argv[1:]

    if cmd not in _COMMANDS:
        print(f"aster: unknown command '{cmd}'\n", file=sys.stderr)
        print(_help_text(), file=sys.stderr)
        sys.exit(2)

    from aster.service.deploy import DeployConfigError, DeployStartupError
    from aster.service.deploy import main as _serve_main

    try:
        if cmd == "check-artifacts":
            from aster.service.check_artifacts import main as check_main

            sys.exit(check_main(rest))
        _serve_main(rest)
    except DeployConfigError as exc:
        # Deploy config errors are typed library errors; the CLI owns the exit.
        print(f"[aster] ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
    except DeployStartupError as exc:
        print(f"[aster] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
