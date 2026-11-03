"""Rev 9 T1: which characters are Chinese, which faces draw them, and how a run's text is cut into Chinese and other
stretches. Shared by the sample route's reader, planner and fill, and by the T2 line-height floor."""

from __future__ import annotations

DEFAULT_FACE = "Microsoft JhengHei"  # CPython calls and any user agent that is not a Mac, iPhone or iPad
MAC_FACE = "PingFang HK"

# T1: a face covers Chinese when its trimmed name starts with one of these (case-insensitive). Japanese and Korean
# faces are not listed: they lack many Traditional Chinese glyphs.
CJK_FACES = (
    "PingFang", "Heiti", "Songti", "Kaiti", "STHeiti", "STSong", "STKaiti", "Apple LiGothic", "Apple LiSung", "LiHei",
    "LiSong", "BiauKai", "Lantinghei", "Microsoft JhengHei", "Microsoft YaHei", "微軟正黑體", "微软雅黑", "PMingLiU",
    "MingLiU", "新細明體", "細明體", "DFKai-SB", "標楷體", "SimSun", "SimHei", "NSimSun", "宋体", "黑体", "DengXian",
    "等线", "FangSong", "KaiTi", "Noto Sans CJK", "Noto Serif CJK", "Noto Sans TC", "Noto Sans SC", "Noto Sans HK",
    "Noto Serif TC", "Noto Serif SC", "Noto Serif HK", "Source Han", "思源", "Arial Unicode", "GenSen",
    "jf-openhuninn", "LXGW", "Taipei Sans", "cwTeX",
)
_PREFIXES = tuple(f.casefold() for f in CJK_FACES)


def is_chinese(ch: str) -> bool:
    """T1: CJK Unified Ideographs and Extension A, Extensions B to H, Compatibility Ideographs, CJK Symbols and
    Punctuation, Bopomofo, and Halfwidth and Fullwidth Forms without the halfwidth katakana and Hangul (U+FF65 to
    U+FFDC). Emoji, kana and Hangul are not."""
    c = ord(ch)
    return (
        0x3400 <= c <= 0x4DBF
        or 0x4E00 <= c <= 0x9FFF
        or 0x20000 <= c <= 0x323AF
        or 0xF900 <= c <= 0xFAFF
        or 0x3000 <= c <= 0x303F
        or 0x3100 <= c <= 0x312F
        or (0xFF00 <= c <= 0xFFEF and not 0xFF65 <= c <= 0xFFDC)
    )


def has_chinese(text: str) -> bool:
    return any(is_chinese(c) for c in text)


def stretches(text: str) -> list[tuple[bool, str]]:
    """The text cut into maximal stretches of Chinese characters and the rest, in order: (is Chinese, stretch)."""
    out: list[tuple[bool, str]] = []
    for ch in text:
        k = is_chinese(ch)
        if out and out[-1][0] == k:
            out[-1] = (k, out[-1][1] + ch)
        else:
            out.append((k, ch))
    return out


def covers_chinese(face: str) -> bool:
    f = face.strip().casefold()
    return any(f.startswith(p) for p in _PREFIXES)


def needs_split(face: str, text: str) -> bool:
    """T1: a run is cut only when it holds Chinese and its named face does not cover Chinese; a run with no named face
    is written as before."""
    return bool(face.strip()) and not covers_chinese(face) and has_chinese(text)

