"""``aster --version`` reports the installed distribution version."""

import subprocess
import sys

import aster


def test_version_flag_prints_package_version() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "aster.cli", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == f"aster {aster.__version__}"
