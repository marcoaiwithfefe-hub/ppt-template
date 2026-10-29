"""What a QA report was run on: the commit, whether the code under test was changed after it, and
sha256 of each file the report points at (Codex round 1, evidence limits). Untracked outputs
such as G0 renders and C10 downloads can then be matched to the run that judged them."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = [
    "src", "docs", "tests", "fixtures/make_fixtures.py", "fixtures/make_template.py", "qa/provenance.py",
    "qa/g0/run_g0.py", "qa/demo/make_demo.py", "qa/e2e/c10_compare.py", "qa/e2e/privacy_proof.py",
    "qa/c5/run_validator.py", "qa/gemini/check_c15.py", "qa/c12/make_worst.py",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tested(files=()) -> dict:
    git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()  # noqa: E731
    return {
        "commit": git("rev-parse", "HEAD"),
        # code only: the reports these runs write are not part of what they test
        "dirty": git("status", "--porcelain", "--", *CODE),
        "files": {str(Path(f).resolve().relative_to(ROOT)): sha256(f) for f in files},
    }
