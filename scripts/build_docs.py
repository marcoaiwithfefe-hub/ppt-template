"""Copy the deckfill package into docs/ as a zip the page unpacks into Pyodide (spec D1).

Run after any change under src/deckfill: .venv/bin/python scripts/build_docs.py
"""

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "deckfill"
OUT = ROOT / "docs" / "py" / "deckfill.zip"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(SRC.glob("*.py")):
            info = zipfile.ZipInfo(f"deckfill/{path.name}", date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, path.read_bytes())
    print(OUT.relative_to(ROOT), OUT.stat().st_size)


if __name__ == "__main__":
    main()
