# C19 proof list

The page strings that changed after Marco's last Rule 25 proof. Each one waits on his proof before deploy. All of them are in `docs/copy.js`. The text is quoted exactly; `{text}` is filled in by the page.

| Key | Since | Text |
|---|---|---|
| `templateErrors.too_big` | rev 5 caps | 檔案太大，網頁處理唔到（上限 100 MB）。可以喺 PowerPoint 刪走示範投影片，或者壓縮圖片，另存再試。 |
| `templateErrors.no_text_layout` | rev 5 | 呢個範本嘅版面冇標題框，網頁唔知將標題放去邊。請揀一個版面有標題框同內文框嘅範本，例如有「標題及內容」版面嘅範本。 |
| `exampleOutline` | rev 5 | the whole example outline in `docs/copy.js`, lines 32 onwards |
| `warnings.layout_gone` | layout-override fix, reworded for F16 | 之前幫「{text}」揀嘅版面取消咗：嗰張投影片刪咗、改咗標題，或者同名嘅投影片多咗或者少咗。請再揀一次版面。 |
| `warnings.layout_dropped` | layout-override fix | 「{text}」：之前揀嘅版面放唔落呢張投影片而家嘅內容，改返用預設版面。 |

When to expect the two new notes:
- `layout_gone` shows once, after the edit that deletes the overridden slide, changes its title or kind, or changes how many slides share its title. In that last case a slide with the same title may still be there, which is why the note no longer says the slide is gone.
- `layout_dropped` shows while the slide's content no longer fits the layout picked for it. One example: a subtitle line added under a cover that was set to Title Only.
