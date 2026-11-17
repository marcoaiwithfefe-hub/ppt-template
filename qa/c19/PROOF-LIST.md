# C19 proof list

The page strings that changed after Marco's last Rule 25 proof. Each one waits on his proof before deploy. All of them are in `docs/copy.js`. The text is quoted exactly; `{text}` is filled in by the page.

| Key | Since | Text |
|---|---|---|
| `templateErrors.too_big` | rev 5 caps | 檔案太大，網頁處理唔到（上限 100 MB）。可以喺 PowerPoint 刪走示範投影片，或者壓縮圖片，另存再試。 |
| `templateErrors.no_text_layout` | rev 5 | 呢個範本嘅版面冇標題框，網頁唔知將標題放去邊。請揀一個版面有標題框同內文框嘅範本，例如有「標題及內容」版面嘅範本。 |
| `exampleOutline` | rev 5 | the whole example outline in `docs/copy.js`, lines 32 onwards |
| `warnings.layout_gone` | layout-override fix, reworded for F16 and F17 | 之前幫「{text}」揀嘅版面取消咗，因為大綱改咗之後，網頁認唔返係邊張投影片。請再揀一次版面。 |
| `warnings.layout_dropped` | layout-override fix | 「{text}」：之前揀嘅版面放唔落呢張投影片而家嘅內容，改返用預設版面。 |
| `routeSample` | rev 8 | 用範本頁嘅設計 |
| `routeLayout` | rev 8 | 用版面 |
| `routeLineSample` | rev 8 | 會跟範本頁嘅設計砌每張投影片（搵到 {n} 張範本頁）。 |
| `routeLineLayout` | rev 8 | 會用範本嘅版面砌每張投影片。 |
| `routeNote` | rev 8 | 網頁估錯嘅話，撳一下就轉。 |
| `sampleOption` | rev 8 | 範本頁 {k}　{words} |
| `fit.shrunk` | rev 8 | 字細咗 |
| `fit.small_text` | rev 8 QA round 1 | 字細 |
| `fit.grown` | rev 8 QA round 2 | 版面調整 |
| `outlineErrors.too_big` | rev 8 | 做出嚟嘅簡報太大，網頁處理唔到。請減少投影片或者每張嘅點數，再試。 |
| `warnings.subtitle_in_title` | rev 8 | 「{text}」：範本封面冇副題框，副題放咗喺標題下面。 |

When to expect the rev 8 states: 字細咗 shows on a sample-route slide whose text was shrunk to fit its box; 字細 shows when no sample slide of the template can hold that slide's text at a readable size (or a picked one cannot), so the text is small. 版面調整 shows when the page made a slide's text box bigger, into empty space on that slide, so the text fits on fewer slides.

When to expect the two new notes:
- `layout_gone` shows once, after the edit that deletes the overridden slide, changes its title or kind (a section slide that gains its first bullet, for example), or changes how many slides share its title. A slide with the same title may still be there, so the note names no single cause.
- `layout_dropped` shows while the slide's content no longer fits the layout picked for it. One example: a subtitle line added under a cover that was set to Title Only.
