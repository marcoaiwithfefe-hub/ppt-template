// Every string the page shows, in one file, so the copy is proofed in one place (spec D8).
// {name} style holes are filled by the page.

export const COPY = {
  title: "用公司範本出 PPT",
  eyebrow: "免費工具 · 只喺你部電腦行",
  h1a: "筆記變簡報，",
  h1b: "用返公司範本。",
  lede:
    "Gemini 幫你寫大綱，網頁將大綱放入你公司嘅 PowerPoint 範本。每個標題、每一點都喺範本自己嘅格仔，logo、顏色、字體唔郁，下載之後照樣可以改。",
  privacy:
    "範本同簡報唔會離開你部電腦。網頁載入完就唔再連網，熄咗 Wi-Fi 都用得。",
  repoLink: "原始碼",

  loading: "準備緊工具，第一次大約十秒……",
  ready: "準備好。由而家開始，網頁唔會再連網。",
  loadFailed: "載入唔到。請檢查網絡，再撳「再試」。",
  retry: "再試",
  working: "處理緊……",

  step1Label: "第一步",
  step1Title: "叫 Gemini 寫大綱",
  step1Body:
    "撳「複製」，去 Gemini 貼上，再喺下面貼你嘅筆記。Gemini 會俾你一個灰色框，撳框角嘅複製掣。",
  copyPrompt: "複製",
  copied: "已複製",
  openGemini: "開 Gemini",
  step1Note:
    "呢一步會將筆記交俾 Gemini。份嘢唔可以外傳嘅話，跟下面個例子自己打大綱都得。",
  showPrompt: "睇吓要複製嘅字",
  showExample: "大綱例子",
  exampleOutline: [
    "# 匯通物流 2027 年度計劃",
    "營運部 · 內部簡報",
    "",
    "## 三個目標",
    "- 本地送貨準時率：92% 升到 97%",
    "  - 試行 AI 排程",
    "- 葵涌倉存貨周轉：45 日減到 35 日",
    "",
    "## 預算 港幣 800 萬",
    "- 科技 350 萬",
    "- 車隊 300 萬",
    "||",
    "- 科技佔 44%",
    "- 車隊佔 37%",
    "",
    "## 問答",
  ].join("\n"),
  exampleHelp:
    "「# 」係封面標題，下一行係副題。每張投影片用「## 」開頭。「- 」係一點，前面加兩個空格係細一級。一行得「||」就分左右兩欄。「## 」下面冇嘢就係分隔頁。",

  step2Label: "第二步",
  step2Title: "拖公司範本入嚟",
  dropHere: "將範本（.pptx 或 .potx）拖入呢個框",
  orPick: "或者撳呢度揀檔案",
  waitReady: "等工具準備好先",
  foundLayouts: "搵到 {n} 個版面",
  master: "母片 {n}",
  usedFor: "用嚟做",
  classNames: { title: "封面", content: "內容", two: "兩欄", section: "分隔頁", other: "其他" },
  defaultMark: "預設",
  unnamed: "（冇名）",
  changeTemplate: "換範本",

  step3Label: "第三步",
  step3Title: "貼大綱，下載簡報",
  outlinePlaceholder: "喺度貼 Gemini 俾你嘅大綱",
  needTemplate: "先拖範本入第二步",
  slidesHeading: "{n} 張投影片",
  slideNo: "第 {n} 張",
  layoutLabel: "版面",
  fit: {
    fits: "放得落",
    split: "太多，分開咗",
    warned: "有一點太長",
    check: "請喺 PowerPoint 檢查",
  },
  fitNote: "放唔放得落係網頁估計。有標記嘅投影片，下載後請喺 PowerPoint 睇一次。",
  warningsHeading: "請睇吓",
  download: "下載 {name}.pptx",
  reset: "重新開始",
  downloaded: "已下載。可以再改大綱或者版面，再下載一次。",

  templateErrors: {
    legacy_ppt: "呢個係舊式 .ppt 檔。請喺 PowerPoint 開，另存做 .pptx，再拖入嚟。",
    encrypted: "呢個檔案有密碼。請喺 PowerPoint 移除密碼，另存一份再拖入嚟。",
    not_pptx: "呢個唔係 PowerPoint 檔。請揀 .pptx 或 .potx 範本。",
    bad_file: "呢個檔案好似壞咗，網頁讀唔到。請喺 PowerPoint 開一次，另存做新檔再試。",
    too_big:
      "檔案太大，網頁處理唔到（上限 100 MB）。可以喺 PowerPoint 刪走示範投影片，或者壓縮圖片，另存再試。",
    no_text_layout:
      "呢個範本嘅版面冇標題框，網頁唔知將標題放去邊。請揀一個版面有標題框同內文框嘅範本，例如有「標題及內容」版面嘅範本。",
    unknown: "出咗錯，網頁讀唔到呢個範本。請試另一個檔案。",
  },
  outlineErrors: {
    too_long: "大綱太長（上限 50,000 字）。請分開幾份做。",
    no_slides: "搵唔到投影片。每張投影片要用「## 」開頭，例如「## 三個目標」。",
    too_many_slides: "投影片太多（上限 200 張）。請分開幾份做。",
    unknown: "出咗錯，請改吓大綱或者版面再試。",
  },
  warnings: {
    outside_slide: "第 {line} 行唔屬於任何一張投影片，冇放入簡報：{text}",
    second_title: "第 {line} 行係第二個「# 」標題，當咗普通投影片。",
    no_title: "冇「# 」封面標題，所以冇封面；檔名用咗第一張投影片嘅標題。",
    empty_bullet: "第 {line} 行得個符號冇字，略過咗。",
    extra_columns: "第 {line} 行多咗一個「||」。一張投影片最多兩欄，略過咗。",
    columns_outside_slide: "第 {line} 行嘅「||」唔喺任何投影片入面，略過咗。",
    heading_level: "第 {line} 行「###」當咗普通一行字。",
    empty_heading: "第 {line} 行個標題冇字。",
    columns_merged: "「{text}」：範本冇兩欄版面，兩欄放咗喺同一個框，右欄跟喺左欄後面。",
    fit_warn: "「{text}」：有一點太長，一張放唔落，冇拆開。下載後請喺 PowerPoint 睇吓。",
    fit_check: "「{text}」：呢個版面網頁估唔到放唔放得落，下載後請喺 PowerPoint 檢查。",
  },

  phoneTitle: "呢個工具要用電腦開",
  phoneBody: "喺手機睇唔到全部功能。撳下面複製連結，喺公司電腦嘅 Chrome 或者 Edge 打開。",
  copyLink: "複製連結",
  phoneSteps: [
    "Gemini 幫你將筆記寫成大綱",
    "拖公司 PowerPoint 範本入網頁",
    "貼大綱，下載用公司範本做好嘅簡報",
  ],

  footer: "Mentron · 開源（MIT）",
};
