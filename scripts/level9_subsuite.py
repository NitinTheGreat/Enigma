"""
Module: scripts/level9_subsuite.py

Freezes a stratified subsample of the Level 7 suite as a declared sample.

Why a sub-suite exists. The full suite is 400 scenarios, 625 situations and
8832 analyses, which is 26496 model calls for a single pass. Level 9 runs
sixteen configurations at five seeds, so a study on the full suite is 80
passes and over two million calls. That is not reachable, and the alternative
to a declared sample is an undeclared one: a --limit that differs between
runs, is recorded nowhere, and makes two results incomparable without anyone
noticing.

What this guarantees. The parent suite hash is verified before anything is
drawn, so a sub-suite can never be cut from a suite that has drifted. The
sample is stratified by regime and drawn with an explicit seed, so it is
reproducible and every regime is represented at equal strength. The result
carries its own hash over exactly the fields the parent hash covers, so a
sub-suite is quotable in the paper the same way the parent is.

The sample is drawn at random within each regime rather than by taking the
first scenarios written. The suite is generated regime by regime in scenario
id order, and the first n of a regime share a generation neighbourhood, so a
prefix is a sample of the generator's early state rather than of the regime.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "Enigma-AIAgent"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from scenarios.generator import Regime, suite_hash  # noqa: E402

from level7_validate import load_suite  # noqa: E402

RESULTS_DIR = PROJECT_ROOT / "results" / "scenarios"
PARENT_HASH = "52b89293b37baff655f97a41a42b67962059c2c96c5a34a716c69af7202f0efc"


def main() -> int:
    """Draw, verify and freeze the stratified sub-suite."""
    parser = argparse.ArgumentParser(description="Level 9 sub-suite freezer.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--per-regime", type=int, default=15)
    parser.add_argument("--suite", type=str, default=str(RESULTS_DIR / "suite.jsonl"))
    parser.add_argument("--out", type=str, default=str(RESULTS_DIR / "sub_suite.jsonl"))
    parser.add_argument(
        "--expect-parent-hash",
        type=str,
        default=PARENT_HASH,
        help="Refuse to cut a sub-suite unless the parent hashes to this.",
    )
    args = parser.parse_args()

    parent = load_suite(Path(args.suite))
    parent_digest = suite_hash(parent)
    if args.expect_parent_hash and parent_digest != args.expect_parent_hash:
        print(f"parent suite hash {parent_digest}")
        print(f"expected          {args.expect_parent_hash}")
        print("refusing to cut a sub-suite from a suite that has drifted")
        return 1

    rng = random.Random(args.seed)
    by_regime: dict[str, list] = defaultdict(list)
    for scenario in parent:
        by_regime[scenario.ground_truth.regime.value].append(scenario)

    taken = []
    shortfalls: dict[str, int] = {}
    for regime in Regime:
        pool = sorted(by_regime[regime.value], key=lambda s: s.scenario_id)
        if len(pool) < args.per_regime:
            shortfalls[regime.value] = len(pool)
        chosen = rng.sample(pool, min(args.per_regime, len(pool)))
        taken.extend(sorted(chosen, key=lambda s: s.scenario_id))

    digest = suite_hash(taken)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for scenario in taken:
            handle.write(json.dumps(scenario.to_dict(), separators=(",", ":")) + "\n")

    signals_total = sum(len(s.signals) for s in taken)
    situations_total = sum(len(s.entities) for s in taken)
    abstained_total = sum(1 for s in taken for sig in s.signals if sig.abstained)
    per_regime = Counter(s.ground_truth.regime.value for s in taken)
    per_category = Counter(s.ground_truth.expected_conclusion for s in taken)

    manifest = {
        "seed": args.seed,
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "sub_suite_hash": digest,
        "parent_suite_hash": parent_digest,
        "parent_suite": str(Path(args.suite).relative_to(PROJECT_ROOT)),
        "parent_scenario_count": len(parent),
        "sampling": "uniform without replacement within each regime",
        "per_regime_requested": args.per_regime,
        "scenario_count": len(taken),
        "signal_count": signals_total,
        "situation_count_under_entity_grouping": situations_total,
        "abstained_signal_count": abstained_total,
        "abstained_signal_fraction": round(abstained_total / signals_total, 4)
        if signals_total
        else 0.0,
        "scenarios_per_regime": dict(sorted(per_regime.items())),
        "scenarios_per_expected_conclusion": dict(sorted(per_category.items())),
        "regimes_short_of_request": shortfalls,
        "scenario_ids": [s.scenario_id for s in taken],
    }
    manifest_path = out_path.with_name(out_path.stem + "_manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"seed {args.seed}   per regime {args.per_regime}")
    print(f"parent suite hash {parent_digest}")
    print(f"sub suite hash    {digest}")
    print(
        f"scenarios {len(taken)}  signals {signals_total}  "
        f"situations {situations_total}  abstained {abstained_total}"
    )
    print(f"per regime {json.dumps(dict(sorted(per_regime.items())))}")
    if shortfalls:
        print(f"regimes short of request {json.dumps(shortfalls)}")
    print(f"written {out_path.relative_to(PROJECT_ROOT)}")
    print(f"written {manifest_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
