"""
Module: scripts/level9_cache_recover.py

Persists the per switch cache measurement that level9_cache_ablation.py made
but failed to write.

What happened. The ablation ran all five configurations to completion and
printed each one's cache statistics, then raised in its report writer on a
relative --cache path, the same defect class already fixed once in
level7_validate.py. The measurement is sound; only the artefact was lost.

Why this is not simply re-run. The misses that the run paid for were written
into the cache as it went, so the cache is now warm for every configuration.
A second run would report a hit rate of 1.0 everywhere and would be measuring
the first run rather than the mechanism. Restoring the cache to its pre
ablation state is not possible because nothing recorded which of its entries
the ablation added.

The figures below are therefore transcribed from the completed run's own
stdout, and every artefact this writes carries a recovered_from_stdout flag
so that no reader mistakes them for a fresh measurement. The run log at
results/budget/cache_ablation_run_log_seed42.jsonl is the authentic 1845
record artefact of the same run and is unaffected.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results" / "budget"

MEASURED = (
    ("baseline", "none", 369, 369, 0, 5.9),
    ("minus_U", "U", 369, 369, 0, 6.2),
    ("minus_S", "S", 369, 259, 110, 1016.2),
    ("minus_A", "A", 369, 345, 24, 233.8),
    ("minus_P", "P", 369, 369, 0, 5.6),
)


def main() -> int:
    """Write the recovered per switch cache figures as JSON and CSV."""
    parser = argparse.ArgumentParser(description="Recover the cache ablation report.")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    for name, ablated, lookups, hits, misses, elapsed in MEASURED:
        rows.append(
            {
                "seed": args.seed,
                "configuration": name,
                "ablated": ablated,
                "lookups": lookups,
                "hits": hits,
                "misses": misses,
                "hit_rate": round(hits / lookups, 4),
                "elapsed_seconds": elapsed,
                "seconds_per_model_call": round(elapsed / misses, 3) if misses else 0.0,
            }
        )

    non_baseline = [r for r in rows if r["configuration"] != "baseline"]
    pooled_lookups = sum(r["lookups"] for r in non_baseline)
    pooled_hits = sum(r["hits"] for r in non_baseline)
    pooled_misses = sum(r["misses"] for r in non_baseline)

    report = {
        "seed": args.seed,
        "recovered_at_utc": datetime.now(timezone.utc).isoformat(),
        "recovered_from_stdout": True,
        "provenance": (
            "Transcribed from the completed run of level9_cache_ablation.py, "
            "which measured all five configurations and then raised in its "
            "report writer. The run log beside this file is that run's own "
            "artefact and is authentic."
        ),
        "model": "gemini-2.5-flash",
        "suite": "results/scenarios/suite.jsonl",
        "slice": "one scenario per regime, s00000 s00100 s00200 s00300",
        "run_log": "results/budget/cache_ablation_run_log_seed42.jsonl",
        "configurations": rows,
        "pooled_excluding_baseline": {
            "lookups": pooled_lookups,
            "hits": pooled_hits,
            "misses": pooled_misses,
            "hit_rate": round(pooled_hits / pooled_lookups, 4),
        },
        "comparison": {
            "l6_8_mock_upper_bound": 0.936,
            "l6_8_first_iteration_floor": 0.31,
        },
        "reading": (
            "U and P change no prompt and hit at 1.0, exactly as L6.8 predicts, "
            "because persistence affects only convergence gating and the "
            "existing hypothesis context already filters UNKNOWN out. S and A "
            "both alter the confidences printed into the next iteration's "
            "prompt and are the only switches that cost model calls. The "
            "pooled rate is the figure a Level 9 budget may use."
        ),
    }

    json_path = RESULTS_DIR / f"cache_ablation_real_seed{args.seed}.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    csv_path = RESULTS_DIR / f"cache_ablation_real_seed{args.seed}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    for row in rows:
        print(
            f"{row['configuration']:<10} ablated {row['ablated']:<5} "
            f"lookups {row['lookups']:>4} hits {row['hits']:>4} "
            f"misses {row['misses']:>4} hit rate {row['hit_rate']:<7} "
            f"{row['elapsed_seconds']:>8.1f}s"
        )
    print()
    print(
        f"pooled excluding baseline  lookups {pooled_lookups}  "
        f"hits {pooled_hits}  misses {pooled_misses}  "
        f"hit rate {report['pooled_excluding_baseline']['hit_rate']}"
    )
    print(f"L6.8 mock upper bound 0.936   L6.8 first iteration floor 0.31")
    print()
    print(f"written {json_path.relative_to(PROJECT_ROOT)}")
    print(f"written {csv_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
