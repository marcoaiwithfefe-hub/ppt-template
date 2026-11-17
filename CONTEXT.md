# Context

Glossary for the PPT template gift. Code, tests and page copy use these terms unchanged
(spec `Projects/ai-agency/specs/2026-10-29-ppt-template-gift-design.md`, rev 4).

- **outline**: the plain-text deck plan in the outline format (spec D2). Written by Gemini or by hand.
- **template**: the user's `.pptx` or `.potx` file. Its masters, layouts and theme are the look.
- **layout class**: what a layout is used for: `title`, `content`, `two`, `section`, or `other` (D3).
- **placeholder**: a text box defined on a layout (title, subtitle, body). Text goes only into placeholders.
- **decoration**: everything on masters and layouts that is not a placeholder: logos, bars, footers drawn as shapes.
- **fill**: making the deck: template in, outline in, `.pptx` out.
- **continuation slide**: an extra slide made when a slide has more bullets than the cap, or more text than its box is estimated to hold (D5).
- **prompt route / skill route**: getting the outline by pasting the prompt from the page, or by the installed Gemini skill.

Terms the code adds:

- **plan**: one entry per output slide (layout, content, continuation flag, fit status). Made only by `plan_deck`; `fill` refuses any other.
- **fit status**: `fits`, `split`, `warned` (one paragraph too long for its box), `check` (a box the estimate does not model).
- **destination**: the placeholder a piece of a slide goes to on a given layout. A layout is compatible with a slide when every piece has one.
- **ready**: the moment the page has loaded Python, the fill module and the fonts, and locks the network off.

Terms rev 8 adds (the sample-slide route, spec D11 and D12):

- **route**: how the deck is built. `layout`: from the template's layouts (D3 to D5). `sample`: each new slide is a copy of one of the template's sample slides with the outline's words in its own boxes (D12). The page picks one by D11 and offers the other with a switch.
- **sample slide**: a slide the template file already holds. It is usable when it has a title destination, holds no chart, table or diagram, is not hidden, and is not an instruction or closing slide. Its override id is `s<k>`, k its 1-based position in the file.
- **title region**: a sample slide's logical title: the anchor (the text box with the largest effective size, then top-most, then left-most) plus the one-word fragments chained to it on the same line or stacked. The title goes into the region's first box, widened to the union of the region.
- **label**: a body box whose whole sample text is digits, spaces and `.,:/%-+$` (6 characters at most), or a single symbol or arrow. Never a destination; its text is cleared on the copy.
- **slot group**: 2 or more body boxes with the same effective size, widths within 10%, and a shared top or left edge (within 2% of the slide). When the group's size equals the slide's number of level-1 bullets, each bullet goes into its own slot.
- **donor run**: the first run or field of a box's first paragraph. Written paragraphs copy its paragraph's properties and written runs copy its run properties; its resolved size is the box's effective size.
- **effective size**: the donor run's size resolved through the run, the paragraph, the box's list style, the layout and master placeholders (or the presentation's default text style for a free text box), else 18 pt.
- **shrink**: on the sample route, a box whose text does not fit gets an explicit size on every written run, in 5% steps on a half-point grid, never below 70% of its effective size (the floor). Fit states add `shrunk` (字細咗); a slide can carry several states.

Terms QA round 1 adds (spec "Rev 8 QA round 1"):

- **readability bar**: a destination's written size, after any shrink, against the slide height: 4% for a title, 2% for every body destination (subtitle, body, slot). A candidate sample meets the bars when every destination on every slide it makes does.
- **chip**: a cleared shape with a fill or line under 8% of the slide area (a label tile, an unused small text box). It goes whole on the copy.
- **backing**: a text-free shape with a fill or line, under 8% of the slide, that holds at least 80% of a cleared text box's area. It goes with its text. Nothing behind a destination that kept its text goes.
- **small_text**: the per-slide state (字細 on the page) when no candidate meets the bars, or a picked sample does not.

Terms code review round 1 adds:

- **unreadable sample**: a sample slide whose reading raised (a malformed attribute, an unresolved reference). It is never usable on either route; why it failed stays in the template info.
- **merged variant**: a two-column slide built on a sample with its columns merged into that sample's largest body box. S2 compares the best readable merged variant with the best readable two-column build, including the merged variant of a sample that has two column boxes.
