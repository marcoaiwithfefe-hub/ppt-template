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
