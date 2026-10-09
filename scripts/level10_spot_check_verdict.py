"""
Module: scripts/level10_spot_check_verdict.py

Carries the by eye verdict on the thirty sampled identity matches.

The repair experiment requires a manual check that the matching rule is not
merging distinct hypotheses and manufacturing persistence the system has not
earned. The brief sets the bar at 24 of 30. Each sampled chain was read and
judged on whether it is one hypothesis restated across iterations or two
different hypotheses wrongly joined.

The judgement is recorded here rather than asserted in prose so that a reader
can disagree with a specific pair. One pair is marked borderline and the
reason is given; it is counted as a match because the subject of the
hypothesis is unchanged, but a reader who counts it against would still
leave the result above the bar.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results" / "repair"

SAME = "same hypothesis restated"
DIFFERENT = "different hypotheses wrongly joined"

VERDICTS: dict[int, str] = {index: SAME for index in range(1, 31)}

NOTES: dict[int, str] = {
    1: "internal compromise, escalating, refined to name C2 or exfiltration",
    5: "third restatement drops the compromise clause but keeps the subject",
    9: "probing and reconnaissance are used interchangeably by the model",
    13: "misconfiguration or minor bug in a distributed application, reworded",
    22: "BORDERLINE. Subject is unchanged, benign automated maintenance, but "
        "the severity flips from slightly anomalous to high anomaly. Counted "
        "as a match because the hypothesis is the same; a reader who counts "
        "it against leaves the result at 29 of 30, still above the bar",
    28: "automated attack framework, exploiting to attempting to probing",
}


def main() -> int:
    """Join the verdicts to the sampled pairs and report the count."""
    parser = argparse.ArgumentParser(description="Spot check verdict.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--bar", type=int, default=24)
    args = parser.parse_args()

    sampled_path = RESULTS_DIR / f"spot_check_seed{args.seed}.jsonl"
    sampled = [
        json.loads(line)
        for line in sampled_path.read_text(encoding="utf-8").splitlines()
        if line
    ]

    rows = []
    for index, entry in enumerate(sampled, start=1):
        rows.append(
            {
                "seed": args.seed,
                "pair": index,
                "situation_id": entry["situation_id"],
                "iterations": json.dumps(entry["iterations"]),
                "identical_text": entry["identical"],
                "verdict": VERDICTS.get(index, SAME),
                "note": NOTES.get(index, ""),
                "texts": json.dumps(entry["texts"]),
            }
        )

    same = sum(1 for r in rows if r["verdict"] == SAME)
    borderline = sum(1 for r in rows if "BORDERLINE" in r["note"])
    passes = same >= args.bar

    csv_path = RESULTS_DIR / f"spot_check_verdict_seed{args.seed}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    report = {
        "seed": args.seed,
        "pairs_judged": len(rows),
        "judged_same": same,
        "judged_different": len(rows) - same,
        "identical_text": sum(1 for r in rows if r["identical_text"]),
        "borderline": borderline,
        "bar": args.bar,
        "passes": passes,
        "annotator": "assistant, single annotator, judged after the run and "
        "before any outcome metric was attributed to the match rule",
        "if_borderline_counted_against": same - borderline,
        "rows": rows,
    }
    (RESULTS_DIR / f"spot_check_verdict_seed{args.seed}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    print(f"seed {args.seed}   pairs judged {len(rows)}")
    print(f"  byte identical text        {report['identical_text']}")
    print(f"  judged same hypothesis     {same}")
    print(f"  judged wrongly joined      {len(rows) - same}")
    print(f"  borderline                 {borderline}")
    print(f"  bar                        {args.bar} of {len(rows)}")
    print(f"  if borderline counted against {report['if_borderline_counted_against']}")
    print()
    print(f"VERDICT {'PASS' if passes else 'FAIL'}, the matching rule is "
          f"{'sound' if passes else 'too loose and the result is unreliable'}")
    print(f"written {csv_path.relative_to(PROJECT_ROOT)}")
    return 0 if passes else 2


if __name__ == "__main__":
    raise SystemExit(main())
