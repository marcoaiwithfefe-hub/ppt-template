import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
FIX = ROOT / "fixtures" / "out"
OUTLINES = ROOT / "tests" / "outlines"
GOLDENS = ROOT / "tests" / "goldens"
REFERENCE = ROOT / "fixtures" / "reference-outline.md"


def pytest_configure(config):
    # Fixture templates are made by script, never downloaded (spec Testing Decisions).
    if not (FIX / "lying-size.pptx").exists():
        subprocess.run([sys.executable, str(ROOT / "fixtures" / "make_fixtures.py")], check=True, capture_output=True)


@pytest.fixture
def tpl():
    def load(name: str) -> bytes:
        return (FIX / name).read_bytes()

    return load


def outline_text(name: str) -> str:
    path = REFERENCE if name == "reference" else OUTLINES / f"{name}.md"
    return path.read_bytes().decode("utf-8")
