#!/bin/zsh
# Failing-first runs for code review round 1: the base commit's source with this round's whole tests/ folder and
# fixture builder from the working tree.
#   qa/cr1/before.sh <base commit> <out file> <pytest args...>
set -e
ROOT=${0:A:h:h:h}
BASE=$1; OUT=$2; shift 2
T=$(mktemp -d)
git -C "$ROOT" archive "$BASE" | tar -x -C "$T"
rsync -a --exclude __pycache__ "$ROOT"/tests/ "$T"/tests/
cp "$ROOT"/fixtures/make_sample_fixtures.py "$T"/fixtures/
cd "$T"
{ echo "base $BASE ($(git -C "$ROOT" rev-parse --short "$BASE")), tests from working tree at $(git -C "$ROOT" rev-parse --short HEAD), scratch $T"; \
  "$ROOT"/.venv/bin/python -m pytest -q -p no:cacheprovider "$@" 2>&1 | grep -E "^(FAILED|ERROR|E  .*(C2[0-9]|F[0-9]))|passed|failed|error" | cut -c1-400; } > "$ROOT/$OUT" || true
echo "$T"
