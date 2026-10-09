"""
Module: scripts/verify_hashes.py

Verifies that the frozen inputs a reproduction depends on have not drifted.

Every number in the paper is computed over one of two artefacts: the Level 7
suite of 400 scenarios, and the Level 9 sub-suite of 40 drawn from it. Both
carry a content hash over their ground truth, parameters, entities, sources
and signals. If either hash has moved, nothing downstream is comparable to
what the paper reports, and the reproduction should stop rather than produce
numbers that look right.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "Enigma-AIAgent"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from scenarios.generator import suite_hash  # noqa: E402

from level7_validate import load_suite  # noqa: E402

SCENARIOS_DIR = PROJECT_ROOT / "results" / "scenarios"
RESULTS_DIR = PROJECT_ROOT / "results" / "reproduce"

EXPECTED = {
    "suite.jsonl": "52b89293b37baff655f97a41a42b67962059c2c96c5a34a716c69af7202f0efc",
    "sub_suite.jsonl": "a2b37f29b163ea310586f3073e88bddd5f0628667ba0c0595ddfa88d708c3911",
}


def main() -> int:
    """Check each frozen suite against the hash the paper quotes."""
    parser = argparse.ArgumentParser(description="Verify frozen input hashes.")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    ok = True
    for name, expected in EXPECTED.items():
        path = SCENARIOS_DIR / name
        if not path.is_file():
            rows.append({"seed": args.seed, "artefact": name, "expected": expected,
                         "actual": "absent", "matches": False})
            ok = False
            continue
        scenarios = load_suite(path)
        actual = suite_hash(scenarios)
        matches = actual == expected
        ok = ok and matches
        rows.append(
            {
                "seed": args.seed,
                "artefact": name,
                "scenarios": len(scenarios),
                "signals": sum(len(s.signals) for s in scenarios),
                "situations": sum(len(s.entities) for s in scenarios),
                "expected": expected,
                "actual": actual,
                "matches": matches,
            }
        )

    csv_path = RESULTS_DIR / f"hashes_seed{args.seed}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    (RESULTS_DIR / f"hashes_seed{args.seed}.json").write_text(
        json.dumps({"seed": args.seed, "all_match": ok, "artefacts": rows}, indent=2),
        encoding="utf-8",
    )

    for row in rows:
        print(
            f"  {row['artefact']:<18} {row.get('scenarios', '?'):>4} scenarios  "
            f"{'MATCHES' if row['matches'] else 'DRIFTED'}  {row['actual'][:16]}"
        )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
