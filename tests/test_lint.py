import subprocess
import sys


def test_ruff_check():
    """
    Test that ruff check passes without errors.
    """
    try:
        subprocess.run([sys.executable, "-m", "ruff", "check", "."], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Ruff check failed:\n{e.stdout}\n{e.stderr}")
        assert False, f"Ruff check failed with exit code {e.returncode}"


def test_ruff_format():
    """
    Test that ruff format makes no changes to the codebase.
    """
    try:
        subprocess.run(
            [sys.executable, "-m", "ruff", "format", ".", "--check"], check=True, capture_output=True, text=True
        )
    except subprocess.CalledProcessError as e:
        print(f"Ruff format check failed:\n{e.stdout}\n{e.stderr}")
        assert False, f"Ruff format check failed with exit code {e.returncode}, indicating changes are needed."
