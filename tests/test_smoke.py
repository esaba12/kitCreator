"""Phase 0 smoke tests — import checks and CLI entry point."""
import importlib
import subprocess
import sys


def test_imports():
    for module in ["kitforge", "kitforge.cli", "kitforge.config", "kitforge.cache"]:
        importlib.import_module(module)


def test_cli_help():
    result = subprocess.run(
        [sys.executable, "-m", "kitforge.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "kitforge" in result.stdout.lower()
