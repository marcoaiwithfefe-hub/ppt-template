#!/usr/bin/env bash
# C15: the outline prompt on Gemini 3.8 Flash through agy, three notes, raw outputs saved.
set -u
cd "$(dirname "$0")/../.."
for n in wui-tung-report english-update meeting-summary; do
  brief="Use no tools: answer directly from the text below.

$(cat docs/prompt.txt)

$(cat fixtures/notes/$n.md)"
  printf '%s' "$brief" > qa/gemini/$n.brief.txt
  env -u GOOGLE_CLOUD_PROJECT agy -p "$brief" --model gemini-3.8-flash-medium --print-timeout 6m > qa/gemini/$n.out.txt 2> qa/gemini/$n.err.txt
  echo "$n exit $? $(wc -c < qa/gemini/$n.out.txt) bytes"
done
