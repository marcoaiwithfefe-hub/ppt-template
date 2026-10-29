"""The QA runners fail when their evidence is incomplete (Codex round 1, F13 and F14)."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(script, *args):
    return subprocess.run([sys.executable, str(ROOT / script), *args], cwd=ROOT, capture_output=True, text=True)


def test_f13_validator_runner_fails_on_a_missing_required_output(tmp_path):
    manifest = json.loads((ROOT / "qa" / "c5" / "manifest.json").read_text())
    manifest["required"] = [{"family": "test", "template": "fixtures/out/typed.pptx", "output": "qa/e2e/not-there.pptx"}]
    m = tmp_path / "manifest.json"
    m.write_text(json.dumps(manifest))
    r = run("qa/c5/run_validator.py", "--manifest", str(m))
    assert r.returncode == 1 and "MISSING qa/e2e/not-there.pptx" in r.stdout


def test_f13_complete_manifest_without_the_sdk_is_not_run(tmp_path):
    manifest = json.loads((ROOT / "qa" / "c5" / "manifest.json").read_text())
    manifest["required"] = [{"family": "D10", "template": "fixtures/wui-tung-template.pptx", "output": "qa/demo/wui-tung-deck.pptx"}]
    m = tmp_path / "manifest.json"
    m.write_text(json.dumps(manifest))
    r = run("qa/c5/run_validator.py", "--manifest", str(m))
    if (ROOT / "tools" / "dotnet" / "dotnet").exists():
        return  # the SDK is installed; this case is about the runner without it
    assert r.returncode == 2 and "NOT RUN" in r.stdout


def test_f14_numbers_compare_as_tokens():
    sys.path.insert(0, str(ROOT / "qa" / "gemini"))
    import check_c15

    assert check_c15.missing_numbers("增長 14%，客戶 14 個", "增長 114%，客戶 114 個") == ["14", "14%"]
    assert check_c15.missing_numbers("港幣 800 萬", "## 預算\n- 港幣 800 萬") == []


def test_f14_a_missing_case_fails_the_run(tmp_path):
    for name in ("wui-tung-report", "english-update"):  # meeting-summary left out
        (tmp_path / f"{name}.out.txt").write_text((ROOT / "qa" / "gemini" / f"{name}.out.txt").read_text())
    r = subprocess.run([sys.executable, str(ROOT / "qa" / "gemini" / "check_c15.py")], cwd=ROOT, capture_output=True,
                       text=True, env={**__import__("os").environ, "C15_DIR": str(tmp_path)})
    assert r.returncode == 1 and "MISSING meeting-summary" in r.stdout
