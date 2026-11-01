# Anti-slop scan triage

Scan: `node ~/.claude/skills/kill-ai-slop/scripts/scan.mjs docs`, run once after the page build (raw output in `qa/slop-scan.txt`). 2 hits, both kept on purpose. No fix made.

| tell | where | verdict | why |
|---|---|---|---|
| 09 decorative strikes and highlights | `docs/style.css` `.link-btn` underline | kept | The underline marks the three text-style buttons (重新開始, 換範本, 再試) as clickable. That is the taxonomy's own exception, underline for links, not decoration. |
| 12 emoji everywhere | `docs/index.html` Gemini link `↗` | kept | A typographic arrow, the same `.arr` pattern mentron.hk uses on its buttons. The `↗` is a pre-declared false-positive class on Mentron work (root Rule 27). It is the only symbol on the page. |

Checked by eye against the other 21 tells before the first render: one cobalt accent from the Mentron palette, flat ink ground with hairline rules, square corners on every element (no nesting radius), no shadows, no gradients, no icon tiles, no badges, no status dot halo (the status mark is a flat 8 px square plus a word), monospace only in the outline box and the code previews.

## Rev 8 and QA round 1 rescan

Scan run once at the end of the rev 8 QA round 1 work (raw output in `qa/slop-scan-rev8.txt`): the same 2 hits as the first scan, same lines, same verdicts (kept: the `.link-btn` underline marks text-style buttons; `↗` is the pre-declared typographic arrow). The rev 8 page additions (route line and switch, the 範本頁 picker, the fit states 字細咗 and 字細) add no hit. No fix made.
