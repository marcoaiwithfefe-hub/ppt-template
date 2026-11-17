# C14: skill file against Google's Gemini skill format

Fetched on 2026-10-30 (02:05 local, 2026-10-29T15:05Z) with `defuddle parse <url> --md`:

- Format and upload rules: https://support.google.com/gemini/answer/17094296?hl=en ("Create & manage skills for Gemini Apps")
- Writing guidance: https://support.google.com/gemini/answer/17102773?hl=en ("Write effective skills for Gemini Apps")

The file compared is `skill/ppt-outline/SKILL.md`. "Required" means the page states the item as a rule. "Advice" means the page gives it as a tip or best practice.

## Fields

| Item | Page says | Kind | `SKILL.md` | Result |
|---|---|---|---|---|
| File and place | "Your project must include a `SKILL.md` file located in the root (main) folder." Upload a `SKILL.md` file, or a folder or `.zip` with `SKILL.md` in its main folder. (17094296) | required | `skill/ppt-outline/SKILL.md`, at the root of its folder | match |
| Name format | "The skill name inside `SKILL.md` must use all lowercase with words separated by a hyphen" (17094296) | required | `ppt-outline` | match |
| Name wording | "Start with an action statement, or verb." "Avoid vague and generic words, like helper, tools, data." (17102773) | advice | `ppt-outline` is a noun phrase; it uses no generic word | differs from the advice; the name is kept as the spec (D7) and ai-brain-52 set it (decisions.tsv, D7 row) |
| Description length | "1–2 sentence description", "within the 1024 character limit" (17102773) | the 1,024 limit is a limit; the sentence count is advice | 2 sentences, 247 characters | match |
| Description voice | "Start with a third-person capability statement." Not first person ("I can help you") or second person ("You can use this to"). (17102773) | advice | starts "Turns notes, a report or meeting minutes into a slide outline ..." | match |
| Description trigger | "Give specific situations where a skill is useful ... Start the statement with `Use when…`." (17102773) | advice | second sentence: "Use when making a presentation, slides or a PowerPoint deck from notes, especially for filling a company PowerPoint template." | match |
| File types and size | Plain-text files such as `.md` are supported; all uploaded files 100 MB at most (17094296) | required | one `.md` file, 1,665 bytes | match |
| Hidden files | "check for hidden binary files (like `.DS_Store` or `.pyc`) that might cause the upload to fail" (17094296) | advice | the folder holds `SKILL.md` only (checked by `tests/test_c14_copy.py`) | match |
| Scripts | Scripts that need the internet are not supported (17094296) | required | no scripts | match |
| Header syntax | Neither page states how `name` and `description` are written inside `SKILL.md`. The manual editor has name, description and instructions fields. | unknown | YAML front matter between `---` lines, `name:` and `description:` | unknown: the pages do not settle it. C16 (upload in the real Gemini app) does |

## Instructions (the body)

The body is the page prompt. It is the same text in `docs/prompt.txt` and `PROMPT.md` (C14 script check), so this pass changes nothing in it. Against the writing advice on 17102773:

- Formatting rules and an output template: present (the code-block template and the Rules list).
- A "common mistakes" section: the Rules list does this job, but it has no heading of that name.
- What to do with missing information: "If the notes do not say something, leave it out." The page's own examples ask the user instead. Leaving it out keeps the outline in the one code block the tool reads.
- Short, one job, steps where the format is strict: present.

## Result

Every required item matches. The name differs from the verb-first advice, and it stays `ppt-outline`. The header syntax is unknown from the pages; C16 settles it. No field was changed.
