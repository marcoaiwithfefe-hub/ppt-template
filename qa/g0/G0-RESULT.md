# Gate G0 result

Run 2026-10-29 on `fixtures/reference-outline.md` (title slide with subtitle, two bullet slides with level 2, one two-column slide, one 8-bullet slide, one section slide). Runner: `qa/g0/run_g0.py`. Raw numbers: `qa/g0/report.json`. Sources: `qa/real-templates/SOURCES.md`.

Verdict: **4 of 5 clean on every G0 part, the C5 validator included.** The validator (Open XML SDK 3.5.1, Office 2016 rules, SDK 10.0.403 installed by Marco on 2026-10-30) ran on f8d9fc9 and found 0 errors in each of the four clean decks (`qa/c5/c5-report.json`). HKUST 15 is refused as `no_text_layout`.

| template | result | C1 text round trip | C3 kept parts | C5 integrity | C5 validator | C6 empty boxes | renders (eye) |
|---|---|---|---|---|---|---|---|
| `edb-mpa2022.pptx` | clean | pass | pass | pass | pass | pass | decoration on every slide, no text past an edge or over another block |
| `elderly-gov-diy.pptx` | clean | pass | pass | pass | pass | pass | same; columns merged into one body (D3 step 4 fallback, warned) |
| `ms-business-proposal.pptx` | clean | pass | pass | pass | pass | pass | same; slide numbers 1 to 6 (cached field text now set per slide, see below) |
| `usc-substitute-fonts-wide.potx` | clean | pass | pass | pass | pass | pass | same; logo on every slide |
| `hkust-template15.potx` | refused `no_text_layout` | n/a | n/a | n/a | n/a | n/a | none |

## Outside the five: HKUST template 14 (spec rev 5)

Rev 5 raised the file cap to 100 MB (2026-10-30), so `hkust-template14.potx` (73.7 MB) now reads. It is reported apart from the five, whose verdict stays as above.

| template | result | C1 text round trip | C3 kept parts | C5 integrity | C5 validator | C6 empty boxes | renders (eye) |
|---|---|---|---|---|---|---|---|
| `hkust-template14.potx` | clean, except 1 validator error the template already has | pass | pass | pass | 1 error, in the template, not added by the fill (see below) | pass | decoration on every slide (campus photo, green bands), no text past an edge or over another block; every slide uses the cover look |

Its content layouts have the same shape as template 15: their title boxes are body placeholders, so all 8 of them, plus `blank page`, are `other`. The only layout with a `title` placeholder is `Cover` (master 2), so the D3 fallback put every slide on `Cover`: titles in its title box, bullets in its body, and the two columns merged with the `columns_merged` warning. The deck is complete and readable, but it is not the content look a person would pick. In the browser its fill is the slowest real-template step in C12, at 2.66 s against the 3 s bar. HKUST's template 16 (58.7 MB) was not downloaded.

HKUST 14 validator error: `Sch_UndeclaredAttribute`, "The 'mod' attribute is not declared.", at `/p:sldLayout[1]/p:extLst[1]` in `ppt/slideLayouts/slideLayout9.xml`. It is HKUST's own `<p:extLst mod="1">`, the extension list that holds the layout's slide guides (`p15:sldGuideLst`). The unfilled template has the same error, and the fill copies that layout byte for byte, so the fill added nothing. It is not on `qa/c5/allowlist.json`, so the C5 runner reports this deck as FAIL. Whether to allowlist it is an open call; it does not touch the verdict on the five.

## Class picks

- EDB (8 masters, Chinese names): title 標題投影片, content 標題及物件, two 兩項物件, section 章節標題. The 8-bullet slide split 6 plus 2 with `（續）`.
- elderly.gov.hk (3 masters, 21 layouts): every layout is `other`. Its only layout with a title and a body, `1_Title and Content`, has two bodies that overlap, so it is not `two`. The D3 fallback used it for every slide, the two columns merged into one body with the `columns_merged` warning, and the subtitle became the body's first paragraph.
- Microsoft: title `Title Slide`, content `Agenda` (the first title plus one body layout in file order), two `Title and two content`, no section layout. The deck's title slide used `Agenda`, because `Title Slide` has no subtitle box, so the subtitle went into the body. `問答` used `Title Slide` (D3 step 4 section fallback).
- USC: title, content, two and section all from the stock names; no fallback.
- HKUST 15: no layout has a `title` or `ctrTitle` placeholder. Its title boxes are body placeholders with a custom prompt, so D3 step 5 refuses it.

## elderly.gov.hk: why level 1 is small and level 2 is large

This is the template's own styling, not a wrong paragraph level from the fill. Each part is one XML line, so the citations name the element path.

- The fill writes the right levels. `ppt/slides/slide2.xml` of the filled deck: level-1 lines are `<a:p>` with no `a:pPr`, so `lvl` is 0; level-2 lines carry `<a:pPr lvl="1"/>` (本地送貨準時率…, then 試行 AI 排程 under `lvl="1"`).
- The layout restyles level 1 only. `ppt/slideLayouts/slideLayout20.xml` (`1_Title and Content`), the `p:sp` holding `<p:ph idx="10"/>`: `a:lstStyle/a:lvl1pPr marL="0" indent="0"` with `<a:buNone/>` and `<a:defRPr sz="1867">` in grey (`tx1`, lumMod 75000, lumOff 25000). It has no `lvl2pPr`.
- Level 2 falls through to the master. `ppt/slideMasters/slideMaster3.xml`, `p:txStyles/p:bodyStyle/a:lvl2pPr`: `<a:buChar char="•"/>` and `<a:defRPr sz="2400">` in `tx1` black. So level 2 is bulleted, black and 24 pt under an 18.67 pt level 1.

## Found and fixed during G0

python-pptx re-sorts relationships by Id and makes absolute targets relative when it saves. Real templates keep them in another order (EDB, elderly.gov.hk, Microsoft and USC all did), so C3 flagged 3 to 16 changed `.rels` parts per template. `fill` now puts the template's own bytes back for every kept part whose meaning is unchanged. A new fixture, `rels-order`, covers it, and an isolated mutation shows the test failing without the fix (`qa/failure-demos/c3-rels-order-*.txt`).

Second fix, from Fable's QA of the renders: a copied slide-number field kept its source slide's cached text, so Quick Look showed 2 on every Microsoft slide and 7 on slide 4. `fill` now writes each slide's own number into the cached text of every `slidenum` field it places. PowerPoint recomputes the field on open either way. C4 checks it on `footer-active`; the mutation demo is `qa/failure-demos/c4-slidenum-text-*.txt`.

## Renders

Local only. They carry third-party branding and the repo goes public, so they are gitignored.

Fable viewed the four clean sheets on 2026-10-30 (sha256 as listed)

- `qa/g0/edb-mpa2022/edb-mpa2022-sheet.png`
- `qa/g0/elderly-gov-diy/elderly-gov-diy-sheet.png`
- `qa/g0/ms-business-proposal/ms-business-proposal-sheet.png`
- `qa/g0/usc-substitute-fonts-wide/usc-substitute-fonts-wide-sheet.png`
- `qa/g0/hkust-template14/hkust-template14-sheet.png` (outside the five)
- per slide: `qa/g0/<template>/renders/slideNN.pptx.png`
