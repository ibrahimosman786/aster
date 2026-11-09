"""Internal HTTP child launched by the config-driven Aster orchestrator.

Reads ASTER_CONFIG through the deploy subpackage (translating YAML into
service settings) and starts the app assembly builds from them.
"""

from aster.service.deploy import DeployConfigError, run_service

if __name__ == "__main__":
    try:
        raise SystemExit(run_service())
    except DeployConfigError as exc:
        raise SystemExit(f"[aster] ERROR: {exc}") from exc
