"""
Module: scripts/repair_mojibake.py

Repairs files whose UTF-8 bytes were decoded as Windows-1252 and re-encoded as
UTF-8, and strips any byte order mark.

PowerShell's Set-Content -Encoding utf8 writes a BOM and, when the file it read
was already UTF-8, mangles every non-ASCII character. A star becomes three
characters, an ellipsis becomes three, an em dash becomes three. The damage is
mechanically reversible: encode the text back to Windows-1252 and decode it as
UTF-8.

The repair is only applied when it round-trips cleanly, so a file containing
genuine Latin-1 characters is left alone rather than corrupted further.
"""

from __future__ import annotations

import argparse
from pathlib import Path

BOM = "﻿"
MOJIBAKE_MARKERS = ("â", "Ã", "Â", "ð\x9f")


def looks_mojibaked(text: str) -> bool:
    """True when the text contains the signature of a double encoding."""
    return any(marker in text for marker in MOJIBAKE_MARKERS)


def repair(text: str) -> tuple[str, bool]:
    """Attempt the reverse transformation.

    Args:
        text: File contents decoded as UTF-8.

    Returns:
        The repaired text and whether a repair was applied.
    """
    if not looks_mojibaked(text):
        return text, False
    try:
        candidate = text.encode("cp1252", errors="strict").decode("utf-8", errors="strict")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text, False
    if looks_mojibaked(candidate):
        return candidate, True
    return candidate, True


def main() -> None:
    """Repair every file given, reporting what changed."""
    parser = argparse.ArgumentParser(description="Repair double-encoded text files.")
    parser.add_argument("files", type=Path, nargs="+")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    for path in args.files:
        raw = path.read_bytes()
        had_bom = raw.startswith(BOM.encode("utf-8"))
        text = raw.decode("utf-8-sig")

        repaired, changed = repair(text)
        needs_write = changed or had_bom

        status = []
        if had_bom:
            status.append("stripped BOM")
        if changed:
            status.append("repaired mojibake")
        if not status:
            status.append("no change needed")

        print(f"{path.name}: {', '.join(status)}")

        if changed:
            for before, after in (("â˜…", "star"), ("â€¦", "ellipsis"), ("â€”", "em dash")):
                if before in text:
                    print(f"    {before!r} -> {after}")

        if needs_write and not args.dry_run:
            path.write_bytes(repaired.encode("utf-8"))


if __name__ == "__main__":
    main()
