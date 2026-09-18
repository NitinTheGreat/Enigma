"""
Module: scripts/level7_validate.py

Runs the unmodified system against the frozen suite and scores the result.

What this validates and what it does not. With no Gemini key present, the
hypothesis generation node falls back to the three fixed strings at
nodes.py:200-202. Everything downstream of generation is the real system:
the sanity gate, evaluation, belief inertia, convergence, the epistemic
controls and the run logger. So this run validates the scoring machinery and
the discriminating power of the suite. It does not validate reasoning quality,
and the correct conclusion rate it reports is a property of the fallback, not
of the reasoner. Rerun once a key exists.

To separate those two things, a reference reasoner is also scored. It sees
exactly what the reasoning graph sees, the aggregated context of evidence
count, source diversity, mean anomaly and burst, and applies simple rules. If
the suite were too easy, that reference would score at ceiling. If it were too
hard, nothing would separate it from always abstaining. Both degenerate cases
are reported explicitly rather than left for a reader to infer.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "Enigma-AIAgent"))

from enigma_reason.domain.signal import Signal  # noqa: E402
from enigma_reason.graph.builder import EpistemicControls  # noqa: E402
from enigma_reason.observability.manifest import build_run_manifest, write_manifest  # noqa: E402
from enigma_reason.observability.run_log import RunLogWriter, text_hash  # noqa: E402
from enigma_reason.replay.offline import OfflineReplay, mock_llm_factory  # noqa: E402
from enigma_reason.store.correlation import EntityCorrelation  # noqa: E402
from scenarios.generator import (  # noqa: E402
    CATEGORIES_BY_NAME,
    NEVER_SUFFICIENT,
    GroundTruth,
    Regime,
    Scenario,
    ScenarioParameters,
)
from scenarios.scoring import OutcomeMetrics, aggregate, score_run  # noqa: E402

RESULTS_DIR = PROJECT_ROOT / "results" / "scenarios"
METRIC_NAMES = (
    "correct_conclusion_rate",
    "false_conclusion_rate",
    "abstention_rate",
    "appropriate_abstention_rate",
    "inappropriate_abstention_rate",
    "premature_convergence_rate",
    "single_iteration_conclusion_rate",
    "mean_iterations_to_termination",
)


def load_suite(path: Path) -> list[Scenario]:
    """Rebuild scenarios from the frozen suite file."""
    scenarios: list[Scenario] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            truth = row["ground_truth"]
            scenarios.append(
                Scenario(
                    scenario_id=row["scenario_id"],
                    seed=row["seed"],
                    ground_truth=GroundTruth(
                        regime=Regime(truth["regime"]),
                        expected_conclusion=truth["expected_conclusion"],
                        should_conclude=truth["should_conclude"],
                        conclusion_keywords=tuple(truth["conclusion_keywords"]),
                        competing_keywords=tuple(truth["competing_keywords"]),
                        sufficient_evidence_count=truth["sufficient_evidence_count"],
                        rationale=truth["rationale"],
                    ),
                    parameters=ScenarioParameters(**row["parameters"]),
                    entities=row["entities"],
                    sources=row["sources"],
                    signals=[Signal.model_validate(s) for s in row["signals"]],
                )
            )
    return scenarios


def stratified_sample(scenarios: list[Scenario], limit: int) -> list[Scenario]:
    """Take an equal share from each regime.

    The suite is written regime by regime, so slicing the first n scenarios
    returns one regime and reports every abstention metric as zero for reasons
    that have nothing to do with the system under test.
    """
    per_regime = max(1, limit // len(Regime))
    taken: list[Scenario] = []
    for regime in Regime:
        matching = [s for s in scenarios if s.ground_truth.regime is regime]
        taken.extend(matching[:per_regime])
    return taken


def raising_llm_factory():
    """Return a factory that fails, which is what having no API key does.

    The real `_default_llm_factory` raises when no key is present, and
    `make_generate_hypotheses` catches every exception and substitutes the
    fallback hypotheses. Reproducing that here keeps the validation honest
    about which path it exercised without requiring the key to be absent from
    the environment running it.
    """

    def factory():
        raise RuntimeError("no Gemini API key, reproducing the unconfigured path")

    return factory


def situation_views(scenario: Scenario) -> list[list[Signal]]:
    """Split a scenario into the signal groups entity correlation will form.

    A policy must be scored on what one situation actually sees. A scenario
    spanning three entities becomes three situations, each holding a third of
    the signals, so handing a policy the whole scenario would let it decide
    from evidence no situation ever has, and would put its denominator on
    scenarios while the system under test is scored on situations.
    """
    grouped: dict[str, list[Signal]] = {}
    for signal in scenario.signals:
        key = str(signal.entity) if signal.entity else "none"
        grouped.setdefault(key, []).append(signal)
    return list(grouped.values())


def reference_conclusion(signals: list[Signal], scenario: Scenario) -> tuple[bool, str]:
    """Decide using only what the reasoning graph is allowed to see.

    The rules mirror the aggregated context: conclude when evidence is
    plentiful, drawn from several sources and strongly anomalous, and abstain
    otherwise. No scenario label is consulted, so this is a genuine reference
    and not an oracle.
    """
    evidence = len(signals)
    diversity = len({s.source for s in signals})
    mean_anomaly = sum(s.anomaly_score for s in signals) / evidence if evidence else 0.0
    abstained = sum(1 for s in signals if s.abstained) / evidence if evidence else 0.0

    if evidence < 6 or diversity < 2:
        return False, "UNKNOWN"
    if abstained > 0.3:
        return False, "UNKNOWN"
    if mean_anomaly < 0.68:
        return False, "UNKNOWN"
    return True, scenario.ground_truth.expected_conclusion


def score_policy(scenarios: list[Scenario], policy) -> OutcomeMetrics:
    """Score any decision policy over the suite.

    Three policies are scored beside the system. Two are trivial and exist to
    bracket the suite: always abstaining and always concluding. If the suite
    were degenerate, a trivial policy would reach ceiling and the measurement
    would be worthless, which is exactly what Level 5 produced. The third is a
    reference that reads only the aggregated context the reasoning graph is
    allowed to see, and marks the score a competent reasoner should be able to
    reach.
    """
    from scenarios.scoring import SituationOutcome

    outcomes = []
    for scenario in scenarios:
        truth = scenario.ground_truth
        for position, signals in enumerate(situation_views(scenario)):
            concludes, named = policy(signals, scenario)
            correct = (
                (concludes and named == truth.expected_conclusion and truth.should_conclude)
                or (not concludes and not truth.should_conclude)
            )
            outcomes.append(
                SituationOutcome(
                    situation_id=f"{scenario.scenario_id}-{position}",
                    scenario_id=scenario.scenario_id,
                    regime=truth.regime.value,
                    expected_conclusion=truth.expected_conclusion,
                    should_conclude=truth.should_conclude,
                    concluded=concludes,
                    abstained=not concludes,
                    conclusion_text_hash=None,
                    matched_expected=concludes and named == truth.expected_conclusion,
                    matched_competitor=False,
                    correct=correct,
                    false_conclusion=concludes and not correct,
                    appropriate_abstention=(not concludes) and not truth.should_conclude,
                    inappropriate_abstention=(not concludes) and truth.should_conclude,
                    premature=concludes and len(signals) < truth.sufficient_evidence_count,
                    iterations=1,
                    evidence_count_at_termination=len(signals),
                    sufficient_evidence_count=truth.sufficient_evidence_count,
                    termination_reason="policy",
                    final_convergence=1.0 if concludes else 0.0,
                )
            )
    return aggregate(outcomes)


def always_abstain(signals: list[Signal], scenario: Scenario) -> tuple[bool, str]:
    """Never conclude, whatever the evidence."""
    return False, "UNKNOWN"


def always_conclude(signals: list[Signal], scenario: Scenario) -> tuple[bool, str]:
    """Always name the scenario's category, whatever the evidence.

    This is the most generous possible guesser, because it is handed the right
    category name for free. Its score is therefore an upper bound on what
    naming without judgement can achieve, and the gap between it and one is the
    part of the suite that requires knowing when not to answer.
    """
    return True, scenario.ground_truth.expected_conclusion


def saturation_report(metrics: OutcomeMetrics, per_regime: dict) -> dict:
    """Flag any metric sitting at floor or ceiling.

    A rate of exactly zero or exactly one measures nothing, which is what
    Level 5 produced and correctly refused. Mean iterations is checked against
    the loop bounds rather than against zero and one.
    """
    findings = []
    for name in METRIC_NAMES:
        value = getattr(metrics, name)
        if name == "mean_iterations_to_termination":
            saturated = value <= 1.0 or value >= 3.0
            bound = "at the one iteration floor or the three iteration cap"
        else:
            saturated = value <= 0.0 or value >= 1.0
            bound = "at floor" if value <= 0.0 else "at ceiling"
        findings.append({
            "metric": name,
            "value": value,
            "saturated": bool(saturated),
            "note": bound if saturated else "within range",
        })

    spread = {}
    for name in METRIC_NAMES:
        values = [getattr(per_regime[r.value], name) for r in Regime]
        spread[name] = {
            "min_across_regimes": round(min(values), 4),
            "max_across_regimes": round(max(values), 4),
            "range": round(max(values) - min(values), 4),
            "discriminates_between_regimes": bool(max(values) - min(values) > 0.05),
        }

    return {
        "per_metric": findings,
        "saturated_metrics": [f["metric"] for f in findings if f["saturated"]],
        "regime_spread": spread,
    }


def main() -> int:
    """Run the system against the suite and score it."""
    parser = argparse.ArgumentParser(description="Level 7 suite validation.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--suite", type=str, default=str(RESULTS_DIR / "suite.jsonl"))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--llm",
        choices=("mock", "fallback"),
        default="fallback",
        help=(
            "fallback is the unmodified system as it stands with no API key, "
            "where generation raises and the three fixed strings at "
            "nodes.py:200-202 are substituted. mock is the Level 6 "
            "deterministic model, whose text varies enough to exercise the "
            "keyword matching in scoring."
        ),
    )
    parser.add_argument("--tag", type=str, default="")
    parser.add_argument(
        "--ablate",
        type=str,
        default="",
        help=(
            "Letters naming epistemic mechanisms to disable, from U, S, A and "
            "P. Used to establish whether a saturated metric is a property of "
            "the suite or of a mechanism, which the generator cannot influence."
        ),
    )
    args = parser.parse_args()

    tag = args.tag or args.llm
    started = datetime.now(timezone.utc)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    scenarios = load_suite(Path(args.suite))
    if args.limit:
        scenarios = stratified_sample(scenarios, args.limit)

    llm_factory = (
        mock_llm_factory(seed=args.seed) if args.llm == "mock" else raising_llm_factory()
    )
    llm_description = (
        "Level 6 deterministic mock model"
        if args.llm == "mock"
        else "fallback hypotheses at nodes.py:200-202, no model call"
    )

    ablated = args.ablate.upper()
    controls = EpistemicControls(
        unknown_hypothesis_enabled="U" not in ablated,
        sanity_gate_enabled="S" not in ablated,
        asymmetric_decay_enabled="A" not in ablated,
        persistence_required="P" not in ablated,
    )

    run_log_path = RESULTS_DIR / f"validation_run_log_{tag}.jsonl"
    if run_log_path.exists():
        run_log_path.unlink()

    descriptions: dict[str, str] = {}
    situation_entities: dict[str, str] = {}

    def harvest(situation, final_state) -> None:
        """Record hypothesis text and the entity a situation belongs to."""
        for hypothesis in final_state.get("hypotheses", []):
            description = str(hypothesis.get("description", ""))
            descriptions[text_hash(description)] = description
        evidence = situation.evidence
        if evidence and evidence[0].entity:
            situation_entities[str(situation.situation_id)] = str(evidence[0].entity)

    analyses = 0
    with RunLogWriter(run_log_path) as writer:
        for scenario in scenarios:
            replay = OfflineReplay(
                llm_factory,
                run_log=writer,
                seed=args.seed,
                correlation=EntityCorrelation(),
                on_analysis=harvest,
                controls=controls,
            )
            result = replay.run(scenario.signals)
            analyses += result.analyses_run
        writer.flush()
        iterations_logged = writer.written
        dropped = writer.dropped

    outcomes, overall, per_regime = score_run(
        run_log_path, scenarios, situation_entities, descriptions
    )
    reference = score_policy(scenarios, reference_conclusion)
    abstain_baseline = score_policy(scenarios, always_abstain)
    conclude_baseline = score_policy(scenarios, always_conclude)
    saturation = saturation_report(overall, per_regime)

    distributions_path = RESULTS_DIR / f"metric_distributions_{tag}.csv"
    with distributions_path.open("w", encoding="utf-8", newline="") as handle:
        writer_csv = csv.writer(handle)
        writer_csv.writerow(["seed", "scope", "metric", "value", "situations"])
        writer_csv.writerow([args.seed, "overall", "situations", overall.situations, overall.situations])
        for name in METRIC_NAMES:
            writer_csv.writerow([args.seed, "overall", name, getattr(overall, name), overall.situations])
        for regime in Regime:
            metrics = per_regime[regime.value]
            for name in METRIC_NAMES:
                writer_csv.writerow(
                    [args.seed, regime.value, name, getattr(metrics, name), metrics.situations]
                )
        for scope, metrics in (
            ("reference_reasoner", reference),
            ("baseline_always_abstain", abstain_baseline),
            ("baseline_always_conclude", conclude_baseline),
        ):
            for name in METRIC_NAMES:
                writer_csv.writerow(
                    [args.seed, scope, name, getattr(metrics, name), metrics.situations]
                )

    outcomes_path = RESULTS_DIR / f"validation_outcomes_{tag}.jsonl"
    with outcomes_path.open("w", encoding="utf-8") as handle:
        for outcome in outcomes:
            handle.write(json.dumps(outcome.to_dict(), separators=(",", ":")) + "\n")

    report = {
        "seed": args.seed,
        "suite": str(Path(args.suite).relative_to(PROJECT_ROOT)),
        "scenarios": len(scenarios),
        "situations_scored": overall.situations,
        "analyses_run": analyses,
        "iterations_logged": iterations_logged,
        "run_log_dropped": dropped,
        "llm": llm_description,
        "epistemic_controls": controls.as_dict(),
        "validates": "scoring machinery and suite discrimination, not reasoning quality",
        "overall": overall.to_dict(),
        "per_regime": {name: m.to_dict() for name, m in per_regime.items()},
        "reference_reasoner": reference.to_dict(),
        "reference_reasoner_per_regime": {
            regime.value: score_policy(
                [s for s in scenarios if s.ground_truth.regime is regime],
                reference_conclusion,
            ).to_dict()
            for regime in Regime
        },
        "baseline_always_abstain": abstain_baseline.to_dict(),
        "baseline_always_conclude": conclude_baseline.to_dict(),
        "suite_is_discriminable": bool(
            reference.correct_conclusion_rate
            > max(
                abstain_baseline.correct_conclusion_rate,
                conclude_baseline.correct_conclusion_rate,
            )
            + 0.05
        ),
        "saturation": saturation,
        "distinct_hypothesis_texts": len(descriptions),
    }
    (RESULTS_DIR / f"validation_run_{tag}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    if args.llm == "fallback":
        (RESULTS_DIR / "validation_run.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        (RESULTS_DIR / "metric_distributions.csv").write_text(
            distributions_path.read_text(encoding="utf-8"), encoding="utf-8"
        )

    manifest = build_run_manifest(
        experiment=f"level7_validate_{tag}",
        seed=args.seed,
        config={"suite": args.suite, "scenarios": len(scenarios)},
        started_at=started,
        project_root=PROJECT_ROOT,
        dataset=Path(args.suite),
        extra={"situations_scored": overall.situations},
    )
    write_manifest(manifest, RESULTS_DIR / f"manifest_validate_{tag}.json")

    print(f"seed {args.seed}   model path: {llm_description}")
    print(f"scenarios {len(scenarios)}  situations scored {overall.situations}  "
          f"analyses {analyses}  iterations logged {iterations_logged}  dropped {dropped}")
    print()
    print(f"{'metric':<36}{'overall':>9}{'clear':>9}{'ambig':>9}{'sparse':>9}{'unknown':>9}{'ref':>9}{'abstain':>9}{'conclude':>9}")
    print("-" * 108)
    for name in METRIC_NAMES:
        print(
            f"{name:<36}{getattr(overall, name):>9}"
            f"{getattr(per_regime['clear'], name):>9}"
            f"{getattr(per_regime['ambiguous'], name):>9}"
            f"{getattr(per_regime['sparse'], name):>9}"
            f"{getattr(per_regime['unknown_attack'], name):>9}"
            f"{getattr(reference, name):>9}"
            f"{getattr(abstain_baseline, name):>9}"
            f"{getattr(conclude_baseline, name):>9}"
        )
    print()
    print("counts", json.dumps(overall.counts))
    print()
    print("suite discrimination, correct conclusion rate by decision policy")
    print(f"  always abstain                 {abstain_baseline.correct_conclusion_rate}")
    print(f"  always conclude                {conclude_baseline.correct_conclusion_rate}")
    print(f"  reference over aggregated context {reference.correct_conclusion_rate}")
    print(f"  system under test              {overall.correct_conclusion_rate}")
    print(f"  suite is discriminable         {report['suite_is_discriminable']}")
    print()
    if saturation["saturated_metrics"]:
        print("SATURATED metrics:", ", ".join(saturation["saturated_metrics"]))
    else:
        print("no metric is at floor or ceiling")
    print()
    print("regime discrimination, range across the four regimes")
    for name in METRIC_NAMES:
        row = saturation["regime_spread"][name]
        print(f"  {name:<36} range {row['range']:>8}  "
              f"discriminates {row['discriminates_between_regimes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
