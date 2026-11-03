===REPORT===

All repository references below are at `bc0291b`. Tests and mutation probes ran from pinned source in memory. No files changed.

| Round 1 item | Status | Code and proving test | Does reverting the fix fail? |
|---|---|---|---|
| F1: missing pair-column fallback | **Closed** | `src/deckfill/sample_plan.py:373-382`; `tests/test_c46_round1.py:177-188` proves pair columns work without built columns, while explicit merge remains merged. | **Yes**, assertion fails with old condition restored. |
| F2: display shrink ranking | **Partly closed** | Steps 7 and 10 now compare correctly. `src/deckfill/sample_plan.py:468-470`; `tests/test_c46_round1.py:153-162`. Mixed normal/display floors introduce R2-1 below. | **Yes**, original ranking makes the test fail. |
| F3: unused body count | **Closed** | Content pairs count written boxes; pair columns count two heads. `src/deckfill/sample_plan.py:266-268,289`; `tests/test_c46_round1.py:165-174`. | **Yes**, restoring `2 * n` fails. Named test covers content pairs, not the separate column-count change. |
| F4: C23 accepts invalid geometry | **Partly closed** | Arbitrary non-pairs are rejected. `tests/sample_look.py:259-328`; `tests/test_c46_round1.py:191-215`. Group eligibility remains too permissive, R2-3 below. | **Yes**, restoring arbitrary-partner acceptance makes the negative test fail. |
| E1: display-title clamp floor | **Closed** | Clamp uses destination’s title floor. `src/deckfill/sample.py:1413-1422`; `tests/test_c46_round1.py:145-150`. | **Yes**, reverting to the ordinary floor fails. |
| C25 weak check | **Closed** | Compares every run against its paragraph’s planned size. `tests/test_c25_fit.py:49-63,123-132`; mixed case at `161-168`. | **Yes**, old flat comparison fails on the subtitle’s 15 runs versus one paragraph. |
| G0c weak check | **Closed** | Donor properties and display bold checked at `qa/g0c/run_g0c.py:63-102`; negative demo at `qa/g0c/donor_negative.py:22-39`. | **Yes for detection**: pinned checker caught three stripped-bold runs and eleven altered Latin donors in memory; previous CJK-only check caught zero. Recorded Canva negative evidence is `qa/g0c/donor-negative.txt:2-12`, not a fresh Canva run here. |

| ID | Severity | Location | Problem | Fix |
|---|---|---|---|---|
| R2-1 | **MAJOR** | `src/deckfill/sample_plan.py:463-470` | Warning penalty depends on the candidate’s title floor. A normal title overflowing at its floor scores **7**, beating a fitting display title at step **10**. Reproduced through `plan_deck`: overflowing 42 pt title selected over fitting 60 pt title. | Make warned/check candidates rank beyond every valid shrink step, consistently across title types. Add a mixed-floor selection test. |
| R2-2 | **MAJOR** | `src/deckfill/sample_plan.py:407-418,437-440,463-470` | Ranking ignores Q9-3’s extra shrink. `need_of_box` measures height only. Reproduced: title written at **54 pt** after orphan prevention scores `(False, 0.0, ...)`, meaning full-size; another candidate written at **57 pt** scores `(True, 1.0, ...)` and loses. Separate from the accepted Canva width issue. | Include orphan-prevention steps in title ranking, while retaining the existing unsplit-body comparison. Test automatic choice between these candidates. |
| R2-3 | **MAJOR** | `tests/sample_look.py:302-312`; compare `src/deckfill/sample.py:820-826` | F4’s comparator checks whether two pairs resemble a group, rather than reconstructing complete D12 slot groups. Reproduced two H/B pairs plus a third unpaired B in their slot group: production reader finds **no pair group**, but C23 accepts an unauthorized H-to-union height change with **zero differences**. Its PASS still cannot prove T5 geometry eligibility. | Independently reconstruct complete D12 groups and require every member to have an eligible H. Add this negative fixture alongside the existing non-pair test. |

Unlikely edge cases:

- **E2-1, MAJOR:** Q9-1 excludes only body boxes. An unclampable title anchor remains selected even when another title candidate fits. Reproduced an off-slide 200 pt decorative box retained as `title/check`, with the in-bounds 120 pt title used as subtitle. Fix: reconsider title selection after rejecting unclampable candidates, retaining fallback only when none remains. Evidence: `src/deckfill/sample.py:1288-1291`; current tests cover subtitle and only-body cases at `tests/test_c46_round1.py:47-62`. **Likelihood: low, requiring oversized off-slide decorative text to win title selection.**

No new XML-safety or privacy regression found in this diff. Input caps and safe parsing remain at `src/deckfill/package.py:121-174` and `src/deckfill/xmlsafe.py:25-45`; sample output budgeting still counts split runs at `src/deckfill/sample_plan.py:894-942`. Recorded layout hashes match all 213 baseline cases, consistent with `qa/rev9/MAP-STATUS.md:45`. Browser, rendering and desktop PowerPoint checks were not rerun.

**Readiness: 6/10.** Three confirmed issues plus one uncommon Q9-1 gap remain. Confidence in findings: **9/10**.

===SPEC_JSON===
{
  "reviewer": "Codex rev9 round 2",
  "spec": "/Users/marcoaiwithfefe/Desktop/AI brain/Projects/ai-agency/specs/2026-10-29-ppt-template-gift-design.md",
  "missing": [
    {
      "entry": "Q9-1",
      "note": "Partly implemented. Spec line 512: \"is not a candidate for a destination role; the next candidate in the existing choice takes that role.\" Filtering intersects edge failures with bodies, so title anchors are never reconsidered. E2-1 reproduces an avoidable title/check result.",
      "evidence": "src/deckfill/sample.py:1288-1291; tests/test_c46_round1.py:47-62"
    }
  ],
  "not_asked": [],
  "built_wrong": [
    {
      "entry": "T5/T6 ranking",
      "note": "R2-1. Spec line 466 retains \"fits at full size, smallest shrink\"; line 473 allows display titles down to their floor \"before it counts as over.\" A normal candidate already over its floor receives penalty 7 and beats a fitting display candidate at step 10.",
      "evidence": "src/deckfill/sample_plan.py:463-470; tests/test_c46_round1.py:153-162"
    },
    {
      "entry": "Q9-3 and ranking",
      "note": "R2-2. Spec line 514 says \"the title steps down in D12's 5% steps\"; line 466 retains \"fits at full size, smallest shrink.\" Placement applies these extra steps, but ranking ignores them. Reproduced 54 pt output ranked as full-size ahead of 57 pt output from the same 60 pt starting size.",
      "evidence": "src/deckfill/sample_plan.py:101-113; src/deckfill/sample_plan.py:407-418; src/deckfill/sample_plan.py:463-470"
    }
  ],
  "unproven": [
    {
      "entry": "C23 / C43",
      "state": "weak_check",
      "gate": "build",
      "note": "R2-3. Spec line 448 requires pairs \"whose B boxes form a D12 slot group\"; line 467 says \"C23 computes the allowed boxes itself from the source sample.\" Comparator accepts pairwise similarity without checking complete group membership. An unpaired third B invalidates the production group but does not prevent C23 accepting its alleged pair geometry.",
      "evidence": "tests/sample_look.py:302-312; src/deckfill/sample.py:820-826; qa/rev9/MAP-STATUS.md:30"
    },
    {
      "entry": "G0c eye / G0b-r9 eye / C46 eye",
      "state": "PENDING",
      "gate": "final_qa",
      "note": "Remaining gate status in the pinned report, not a new failure or a reopening of accepted flags. Spec lines 504-505 and 521 require \"script plus Fable's eye\" with \"final QA (eye)\". Report still records overall eye rows as PENDING; specific accepted rulings do not constitute a recorded overall completion.",
      "evidence": "qa/rev9/REPORT.md:7; qa/rev9/MAP-STATUS.md:18-21"
    },
    {
      "entry": "C17",
      "state": "PENDING",
      "gate": "deploy",
      "note": "Existing deploy gate. Spec line 229: \"the row stays PENDING for Windows until that run exists\". Desktop Windows PowerPoint opening, repair behavior and rendering remain unproven by this review.",
      "evidence": "qa/rev9/MAP-STATUS.md:44; qa/rev9/MAP-STATUS.md:49"
    }
  ]
}