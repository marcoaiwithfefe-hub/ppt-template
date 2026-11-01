#!/bin/zsh
# Failing-first runs for code review round 1: the base commit's source with this round's tests and fixture builder.
#   qa/cr1/before.sh <base commit> <out file> <pytest args...>
set -e
ROOT=${0:A:h:h:h}
BASE=$1; OUT=$2; shift 2
T=$(mktemp -d)
git -C "$ROOT" archive "$BASE" | tar -x -C "$T"
cp "$ROOT"/tests/test_cr1_code_review.py "$ROOT"/tests/sample_oracle.py "$ROOT"/tests/sample_look.py "$T"/tests/ 2>/dev/null || true
for f in "$@"; do [[ -f "$ROOT/$f" ]] && cp "$ROOT/$f" "$T/$f" || true; done
cp "$ROOT"/fixtures/make_sample_fixtures.py "$T"/fixtures/
cd "$T"
{ echo "base $BASE ($(git -C "$ROOT" rev-parse --short "$BASE")), tests from working tree at $(git -C "$ROOT" rev-parse --short HEAD), scratch $T"; \
  "$ROOT"/.venv/bin/python -m pytest -q -p no:cacheprovider "$@" 2>&1 | tail -40; } > "$ROOT/$OUT" || true
echo "$T"
