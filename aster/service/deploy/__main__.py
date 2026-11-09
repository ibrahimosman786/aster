"""Allow ``python -m aster.service.deploy`` as an alias for ``aster serve``."""

from aster.service.deploy import DeployConfigError, main

if __name__ == "__main__":
    try:
        main()
    except DeployConfigError as exc:
        raise SystemExit(f"[aster] ERROR: {exc}") from exc
