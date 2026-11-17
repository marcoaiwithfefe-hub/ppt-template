===REPORT===

Reviewed `acd26e0..135093a`, read-only. Locations below refer to `135093a`. No files changed.

| id | severity | tag | location | problem | fix |
|---|---|---|---|---|---|
| F1 | MAJOR | [claims] | `src/deckfill/sample_plan.py:349-364` | Qualifying pair columns are skipped when `two_dest()` returns `None`. Reproduced with three identical heading/body pairs: sample is two-compatible, `pair_columns()` succeeds, but `build()` merges both columns into one body. Existing fixture’s two-heading slot group masks this branch. | Try pair columns when built columns are absent **or** fail their test, while preserving explicit `merge=True`. Add three-identical-pairs coverage. |
| F2 | MAJOR | [claims] | `src/deckfill/sample_plan.py:436-440` | Ranking still caps shrink at seven steps although display titles now support eleven. Reproduced 100 pt titles fitting at 50 pt and 65 pt: both receive shrink score `7.0`, allowing file order to select smaller text. | Preserve actual display-title shrink steps through ranking. Test competing candidates requiring steps 7 and 10. |
| F3 | MAJOR | [diff] | `src/deckfill/sample_plan.py:245`, `src/deckfill/sample_plan.py:266`, `src/deckfill/sample_plan.py:339-340` | Pair builds count cleared B boxes as used. Content always returns `2*n`; pair columns return `4` despite clearing both B boxes. Reproduced two childless bullets: reported unused count `2`, actual count `4`. This changes candidate selection when earlier ranking keys tie. | Count body-box IDs actually receiving text. Exclude written labels from this count. |
| F4 | MAJOR | [diff] | `tests/sample_look.py:255-273`, `tests/sample_look.py:591-593`, `tests/sample_look.py:647-648` | C23 accepts undeclared geometry as a pair edit. It considers every text shape a possible partner, without T5’s size, overlap, proximity, exclusion or group requirements. Reproduced expansion across two equal-size, horizontally disjoint boxes separated vertically by 150 pt: `look_diff()` returned `[]`. This is a broken QA guard, not evidence that production currently emits that mutation. | Independently identify eligible pairs and groups before allowing their geometry. Add this invalid-pair mutation. |

**Unlikely edge cases**

- **E1, MAJOR [claims]**: `src/deckfill/sample.py:1371-1378` hardcodes a 70% clamp floor, ignoring display titles’ 50% floor at `src/deckfill/sample_plan.py:68-78`. Reproduced a 100 pt title at x = −20 pt: legal clamped box holds a 50 pt Chinese line, yet reader marks it `edge clamp` and retains negative x. Fix: use destination-specific floor. **Likelihood:** uncommon; requires an off-slide display title whose clamped dimensions fit its display floor but fail 70%.

**Verification and limits**

- In-memory probes loaded pinned source only. Browser bundle matches all 13 source modules.
- Recorded privacy logs pass both user agents using `qa/e2e/privacy_proof.py:18-41`. All 213 baseline layout entries match head’s recorded output hashes, supporting `qa/rev9/MAP-STATUS.md:39-43`.
- No new XML-safety or privacy regression identified. Input caps and safe parsing remain in `src/deckfill/package.py:121-174,328-348` and `src/deckfill/xmlsafe.py:25-45`; generated XML retains planning and writing caps at `src/deckfill/sample_plan.py:850-898` and `src/deckfill/sample_fill.py:423-425`.
- Full suite, browser session, performance measurements and native PowerPoint opening were not rerun. Existing reports are evidence, not fresh measurements. Known excluded flags are omitted.

**Readiness: 6/10. Finding confidence: 9/10.** No BLOCKER identified. Normal-path MAJOR findings require another review round after fixes.

Need from you: nothing needed.

===WALKTHROUGH_JSON===
{
  "reviewer": "Codex rev9 round 1",
  "steps": {
    "step-1": {
      "verdict": "holds",
      "note": "User-agent face selection, propagation through plan and fill, conditional face note, and refineNote visibility on both routes match code. Fill recomputes its plan with the supplied face.",
      "evidence": "docs/app.js:15-15; docs/app.js:299-302; docs/app.js:394-400; docs/app.js:410-437; src/deckfill/web.py:96-165; src/deckfill/fill.py:314-318"
    },
    "step-2": {
      "verdict": "holds",
      "note": "Reader records two resolved faces, display flag and donor properties; excludes watermarks from title/body classification; derives echoes, pairs and two-compatibility as described.",
      "evidence": "src/deckfill/sample.py:1202-1260; src/deckfill/sample.py:1287-1295; src/deckfill/sample.py:1301-1338; src/deckfill/sample.py:1471-1476"
    },
    "step-3": {
      "verdict": "partial",
      "note": "Read-time clamp and fallback are accurately described. However, the stated 70% test misses T6 display-title floors: E1 retains an off-slide title although its clamped box holds a line at its applicable 50% floor. Fragmented titles update title_box rather than storing that union in SBox.orig.",
      "evidence": "src/deckfill/sample.py:1371-1411; src/deckfill/sample_plan.py:68-78"
    },
    "step-4": {
      "verdict": "partial",
      "note": "Slot precedence, pair geometry, child placement and label rewriting hold. Two-column fallback is incomplete: pair columns are attempted only when two_dest returned an existing destination, missing F1. Pair builds also miscount cleared bodies as used, F3.",
      "evidence": "src/deckfill/sample_plan.py:224-266; src/deckfill/sample_plan.py:330-364"
    },
    "step-5": {
      "verdict": "partial",
      "note": "Growth search, exact top-left, candidate ordering, group checks and display floor match description. needs reads grown geometry, but downstream rank_key truncates valid display-title shrink scores at seven, contradicting preserved smallest-shrink ranking, F2.",
      "evidence": "src/deckfill/sample_plan.py:298-306; src/deckfill/sample_plan.py:397-440; src/deckfill/sample_plan.py:570-640"
    },
    "step-6": {
      "verdict": "holds",
      "note": "Writer performs maximal run splitting, Chinese property overrides, size writes, line-spacing adjustment and echo wrapping as described. Budget counts split-run properties and markup; final writer also checks actual generated XML bytes.",
      "evidence": "src/deckfill/sample_fill.py:122-172; src/deckfill/sample_fill.py:364-373; src/deckfill/sample_fill.py:423-425; src/deckfill/sample_plan.py:850-883"
    }
  },
  "call_path": {
    "verdict": "partial",
    "note": "New and changed boxes correspond to implementation; no gone boxes are declared. Main forward flow holds. Download edge omits Session.fill replanning and fill's second planning comparison before fill_sample. R3 grow_build also supplies an alternate title-growth path. Claim that ranking stays unchanged is undermined by F2 and F3; two-column branch omits F1's absent-destination case.",
    "evidence": "qa/walkthrough/rev9/walkthrough.json:51-53; src/deckfill/web.py:156-167; src/deckfill/fill.py:314-320; src/deckfill/sample_plan.py:349-364; src/deckfill/sample_plan.py:436-440; src/deckfill/sample_plan.py:622-682"
  },
  "missed": [
    {
      "note": "Pair-compatible samples can lack a built two-column destination; qualifying pair columns are then skipped, F1.",
      "evidence": "src/deckfill/sample_plan.py:349-364"
    },
    {
      "note": "Display shrink steps 7 through 10 collapse to the same ranking score, F2.",
      "evidence": "src/deckfill/sample_plan.py:439"
    },
    {
      "note": "Cleared pair bodies count as used and alter the unused-box ranking, F3.",
      "evidence": "src/deckfill/sample_plan.py:245; src/deckfill/sample_plan.py:266"
    },
    {
      "note": "C23's independent implementation does not establish T5 eligibility. An invalid pair expansion passes the comparator, F4.",
      "evidence": "tests/sample_look.py:255-273; tests/sample_look.py:591-593"
    },
    {
      "note": "Clamp eligibility uses 70% even for display titles with a lower applicable floor, E1.",
      "evidence": "src/deckfill/sample.py:1374; src/deckfill/sample_plan.py:74-78"
    },
    {
      "note": "Generic C25 size comparison assumes one run per paragraph, while T1 can create several. Its listed cases do not exercise the new mixed-script split outputs.",
      "evidence": "tests/test_c25_fit.py:118-144"
    },
    {
      "note": "G0c's general Chinese oracle omits C39's display-bold and donor-property comparisons, so its PASS establishes only part of the referenced C39 rule.",
      "evidence": "qa/g0c/run_g0c.py:54-55; tests/rev9_oracle.py:93-129"
    }
  ]
}
===SPEC_JSON===
{
  "reviewer": "Codex rev9 round 1",
  "spec": "/Users/marcoaiwithfefe/Desktop/AI brain/Projects/ai-agency/specs/2026-10-29-ppt-template-gift-design.md",
  "missing": [],
  "not_asked": [],
  "built_wrong": [
    {
      "id": "F1",
      "severity": "MAJOR",
      "tag": "[spec]",
      "spec_line": 461,
      "quote": "When it does not, and the sample has a pair group of 2 or more pairs, the pair columns below are used if every used H fits at or above the 70% floor with no fit warning.",
      "note": "Absent built columns bypass pair_columns entirely. Three identical heading/body pairs produce a two-compatible sample with qualifying pair columns, yet build merges the columns.",
      "evidence": "src/deckfill/sample_plan.py:349-364"
    },
    {
      "id": "F2",
      "severity": "MAJOR",
      "tag": "[spec]",
      "spec_line": 466,
      "quote": "smallest shrink, fewest body boxes left unused, file order",
      "note": "Display titles may need steps 7 through 10 under T6, but rank_key caps each at 7. Reproduced 65% and 50% titles receiving equal shrink scores.",
      "evidence": "src/deckfill/sample_plan.py:64-78; src/deckfill/sample_plan.py:436-440"
    },
    {
      "id": "F3",
      "severity": "MAJOR",
      "tag": "[spec]",
      "spec_line": 466,
      "quote": "fewest body boxes left unused",
      "note": "Content pair builds subtract two used boxes per pair even when a childless bullet clears B. Pair-column builds subtract four although both B boxes are cleared. Ranking therefore understates unused body boxes.",
      "evidence": "src/deckfill/sample_plan.py:238-245; src/deckfill/sample_plan.py:255-266; src/deckfill/sample_plan.py:336-340"
    },
    {
      "id": "E1",
      "severity": "MAJOR",
      "tag": "[spec]",
      "edge_case": true,
      "spec_line": 441,
      "quote": "under one line of the destination's text at its floor size",
      "related_spec_line": 473,
      "related_quote": "down to 50% of its effective size",
      "note": "Clamp eligibility always tests 70%. A display title whose clamped box fits its legal 50% floor is incorrectly left off-slide with check-this-slide. Uncommon combination of off-slide position and tight clamped dimensions.",
      "evidence": "src/deckfill/sample.py:1371-1378; src/deckfill/sample.py:1396-1401; src/deckfill/sample_plan.py:68-78"
    }
  ],
  "unproven": [
    {
      "entry": "C43 / C23",
      "state": "weak_check",
      "gate": "build",
      "tag": "[spec]",
      "spec_line": 467,
      "quote": "C23 computes the allowed boxes itself from the source sample.",
      "note": "F4: comparator computes unions with arbitrary text shapes rather than eligible T5 partners. An equal-size, disjoint, distant pair mutation passes look_diff. Recorded PASS does not establish that only declared pair edits are accepted.",
      "evidence": "tests/sample_look.py:255-273; tests/sample_look.py:591-593; tests/sample_look.py:647-648; qa/rev9/MAP-STATUS.md:14,28"
    },
    {
      "entry": "C25",
      "state": "weak_check",
      "gate": "build",
      "tag": "[spec]",
      "spec_line": 349,
      "quote": "every size the fill wrote is on the 50 grid and at or above its 70% floor, and equals the size the estimate used",
      "note": "T6 amends the floor, but T1 also changes run count. written_sizes returns one value per run while check_plan expects one per paragraph for shrunk boxes. Correct mixed-script split paragraphs would fail this comparison. Listed generic cases omit the new split-run fixtures, so PASS does not cover this interaction.",
      "evidence": "tests/test_c25_fit.py:49-58; tests/test_c25_fit.py:118-144; qa/rev9/MAP-STATUS.md:30"
    },
    {
      "entry": "G0c",
      "state": "weak_check",
      "gate": "build",
      "tag": "[spec]",
      "spec_line": 504,
      "quote": "every Chinese run passes C39's rule",
      "note": "G0c invokes cjk_problems, which checks face, character grouping, tracking, italic and language but never checks display bold. C39's fixture-specific bold and donor-property checks are separate and are not applied to the Canva outputs. Four recorded PASSes establish a narrower promise.",
      "evidence": "qa/g0c/run_g0c.py:54-55; tests/rev9_oracle.py:93-129; tests/test_c39_c40_type.py:79-94; qa/rev9/MAP-STATUS.md:17"
    },
    {
      "entry": "G0c eye",
      "state": "PENDING",
      "gate": "final_qa",
      "tag": "[spec]",
      "spec_line": 504,
      "quote": "Fable judges each slide against `target-sheet.png` on four points",
      "note": "Visual verdict remains explicitly pending. Later-gate obligation, not an accepted PASS or missing build execution.",
      "evidence": "qa/rev9/MAP-STATUS.md:18"
    },
    {
      "entry": "G0b-r9 eye",
      "state": "PENDING",
      "gate": "final_qa",
      "tag": "[spec]",
      "spec_line": 505,
      "quote": "an eye verdict recorded per slide in the G0b-r9 report",
      "note": "Eye review remains pending. Known script regressions are excluded from this review as requested; this records only the outstanding later gate.",
      "evidence": "qa/rev9/MAP-STATUS.md:20"
    },
    {
      "entry": "C17",
      "state": "PENDING",
      "gate": "deploy",
      "tag": "[spec]",
      "spec_line": 229,
      "quote": "the row stays PENDING for Windows until that run exists",
      "note": "Desktop Windows PowerPoint opening and rendering remain unproven. Rev 8 also adds two sample-route outputs at spec line 357. Schema checks and LibreOffice or Quick Look renders do not close this gate.",
      "evidence": "qa/rev9/MAP-STATUS.md:42,47"
    },
    {
      "entry": "T7 Canto proof",
      "state": "PENDING",
      "gate": "final_qa",
      "tag": "[spec]",
      "spec_line": 480,
      "quote": "copy of record pending Marco's Canto proof at the final QA gate",
      "note": "C45 verifies the implemented line and visibility. Editorial proof remains a separate pending obligation, explicitly named in the walkthrough but absent from the map-status table.",
      "evidence": "qa/walkthrough/rev9/walkthrough.json:122; qa/rev9/MAP-STATUS.md:16"
    }
  ]
}