"""
Module: scripts/level7_example.py

Prints one scenario end to end: what was generated, what a correct reasoner
should conclude, and what the system actually concluded.

Chooses a scenario the system got wrong where the reference reasoner got it
right, because that is the case a reader most needs to see. A worked example
the system happens to pass demonstrates nothing about whether the suite
measures anything.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "Enigma-AIAgent"))

RESULTS_DIR = PROJECT_ROOT / "results" / "scenarios"


def main() -> int:
    """Print a worked example."""
    parser = argparse.ArgumentParser(description="Level 7 worked example.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--tag", type=str, default="mock")
    parser.add_argument("--regime", type=str, default="clear")
    parser.add_argument("--scenario", type=str, default="")
    args = parser.parse_args()

    outcomes = [
        json.loads(line)
        for line in (RESULTS_DIR / f"validation_outcomes_{args.tag}.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]

    if args.scenario:
        chosen = next(o for o in outcomes if o["scenario_id"] == args.scenario)
    else:
        wrong = [
            o for o in outcomes
            if o["regime"] == args.regime and not o["correct"]
        ]
        if not wrong:
            wrong = [o for o in outcomes if o["regime"] == args.regime]
        chosen = wrong[0]

    scenario = None
    with (RESULTS_DIR / "suite.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row["scenario_id"] == chosen["scenario_id"]:
                scenario = row
                break

    if scenario is None:
        print(f"scenario {chosen['scenario_id']} not found in the suite")
        return 1

    signals = scenario["signals"]
    truth = scenario["ground_truth"]
    parameters = scenario["parameters"]

    print(f"seed {args.seed}   model path tag {args.tag}")
    print("=" * 78)
    print(f"SCENARIO {scenario['scenario_id']}")
    print("=" * 78)
    print(f"  regime                  {truth['regime']}")
    print(f"  entities                {scenario['entities']}")
    print(f"  sources                 {scenario['sources']}")
    print(f"  signals                 {len(signals)}")
    print(f"  source diversity        {len(set(s['source'] for s in signals))}")
    print(f"  signal types            {dict(Counter(s['signal_type'] for s in signals))}")
    mean_anomaly = sum(s["anomaly_score"] for s in signals) / len(signals)
    print(f"  mean anomaly            {mean_anomaly:.4f}")
    print(f"  abstained signals       {sum(1 for s in signals if s['abstained'])}"
          f" of {len(signals)}")
    print(f"  burst phase             {parameters['burst_phase']}")
    print(f"  quiet phase             {parameters['quiet_phase']}")
    print(f"  first event             {signals[0]['timestamp']}")
    print(f"  last event              {signals[-1]['timestamp']}")
    print()
    print("  three sample signals")
    for signal in signals[:3]:
        print(f"    {signal['timestamp']}  {signal['signal_type']:<18} "
              f"anomaly {signal['anomaly_score']:.3f}  source {signal['source']:<18} "
              f"abstained {signal['abstained']}")
    print()
    print("-" * 78)
    print("GROUND TRUTH")
    print("-" * 78)
    print(f"  expected conclusion     {truth['expected_conclusion']}")
    print(f"  should conclude         {truth['should_conclude']}")
    print(f"  sufficient evidence     {truth['sufficient_evidence_count']}")
    print(f"  conclusion keywords     {truth['conclusion_keywords']}")
    print(f"  competing keywords      {truth['competing_keywords']}")
    print(f"  rationale               {truth['rationale']}")
    print()
    print("-" * 78)
    print("WHAT THE SYSTEM ACTUALLY CONCLUDED")
    print("-" * 78)
    print(f"  situation               {chosen['situation_id']}")
    print(f"  concluded               {chosen['concluded']}")
    print(f"  abstained               {chosen['abstained']}")
    print(f"  iterations              {chosen['iterations']}")
    print(f"  termination reason      {chosen['termination_reason']}")
    print(f"  final convergence       {chosen['final_convergence']}")
    print(f"  evidence at termination {chosen['evidence_count_at_termination']}")
    print(f"  matched expected        {chosen['matched_expected']}")
    print(f"  matched competitor      {chosen['matched_competitor']}")
    print()
    print(f"  correct                 {chosen['correct']}")
    print(f"  false conclusion        {chosen['false_conclusion']}")
    print(f"  appropriate abstention  {chosen['appropriate_abstention']}")
    print(f"  inappropriate abstention {chosen['inappropriate_abstention']}")
    print(f"  premature convergence   {chosen['premature']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
