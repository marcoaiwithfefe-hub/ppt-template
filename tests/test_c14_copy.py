"""C14: prompt and copy floors (content Rules 140 and 76), and one prompt text in three places."""

import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PERSONA = ["rg", "-n", "-e", "你是", "-e", "你係", "-e", "[Yy]ou are an? "]


def rg(args, paths, cwd=ROOT):
    return subprocess.run(args + paths, cwd=cwd, capture_output=True, text=True)


def test_no_persona_line():
    r = rg(PERSONA, ["docs", "skill", "PROMPT.md"])
    assert r.returncode == 1, r.stdout  # rg exits 1 when nothing matches


def test_persona_search_finds_a_planted_line(tmp_path):
    scratch = tmp_path / "copy"
    shutil.copytree(ROOT / "skill", scratch / "skill")
    (scratch / "PROMPT.md").write_text((ROOT / "PROMPT.md").read_text() + "\nYou are an assistant.\n")
    r = rg(PERSONA, ["skill", "PROMPT.md"], cwd=scratch)
    assert r.returncode == 0 and "You are an assistant" in r.stdout


def test_no_banned_word():
    r = rg(["rg", "-n", "指令"], ["docs", "README.md", "skill", "PROMPT.md"])
    assert r.returncode == 1, r.stdout


def prompt_in_md() -> str:
    text = (ROOT / "PROMPT.md").read_text(encoding="utf-8")
    return re.search(r"````text\n(.*?)````", text, re.S).group(1)


def skill_body() -> str:
    text = (ROOT / "skill" / "ppt-outline" / "SKILL.md").read_text(encoding="utf-8")
    return text.split("\n---\n", 1)[1].lstrip("\n")


def test_one_prompt_text_everywhere():
    page = (ROOT / "docs" / "prompt.txt").read_text(encoding="utf-8")
    assert prompt_in_md() == page
    assert skill_body() == page


def test_skill_file_matches_google_format():
    """support.google.com/gemini/answer/17094296 and 17102773: SKILL.md at the folder root, a
    lowercase hyphenated name, a third-person description starting with what it does, a 'Use when'
    clause, at most 1024 characters."""
    text = (ROOT / "skill" / "ppt-outline" / "SKILL.md").read_text(encoding="utf-8")
    head = text.split("\n---\n", 1)[0]
    assert head.startswith("---\n")
    fields = dict(line.split(": ", 1) for line in head.splitlines()[1:])
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", fields["name"])
    desc = fields["description"]
    assert len(desc) <= 1024 and "Use when" in desc
    assert not re.match(r"(I |You )", desc)
    assert sorted(p.name for p in (ROOT / "skill" / "ppt-outline").iterdir()) == ["SKILL.md"]
