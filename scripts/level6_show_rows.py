"""
Module: scripts/level6_show_rows.py

Prints consecutive run log rows for one situation, for the Level 6 done check.

Selects the situation whose dominant hypothesis confidence moves most across
its first rows, because a triple where nothing changes shows that the writer
runs but not that it captures belief revision, which is the property Level 7
scores.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def dominant_confidence(row: dict) -> float:
    """Return the confidence of the row's dominant hypothesis."""
    leader = row.get("dominant_hypothesis_id")
    for hypothesis in row.get("hypotheses", []):
        if hypothesis.get("hypothesis_id") == leader:
            return float(hypothesis.get("confidence") or 0.0)
    return 0.0


def main() -> int:
    """Find and print one situation's consecutive iteration rows."""
    parser = argparse.ArgumentParser(description="Show run log rows for one situation.")
    parser.add_argument("--path", type=str, required=True)
    parser.add_argument("--rows", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    with Path(args.path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            grouped[(row["run_id"], row["situation_id"])].append(row)

    best_key: tuple[str, str] | None = None
    best_spread = -1.0
    for key, rows in grouped.items():
        if len(rows) < args.rows:
            continue
        ordered = sorted(rows, key=lambda r: r["iteration"])[: args.rows]
        if [r["iteration"] for r in ordered] != list(range(1, args.rows + 1)):
            continue
        confidences = [dominant_confidence(r) for r in ordered]
        spread = max(confidences) - min(confidences)
        if spread > best_spread:
            best_spread, best_key = spread, key

    if best_key is None:
        print(f"no situation in {args.path} has {args.rows} consecutive iterations")
        return 1

    rows = sorted(grouped[best_key], key=lambda r: r["iteration"])[: args.rows]
    print(f"seed {args.seed}")
    print(f"situation {best_key[1]}")
    print(f"dominant confidence spread across {args.rows} iterations: {best_spread:.4f}")
    print()
    for row in rows:
        print(json.dumps(row, indent=2))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
