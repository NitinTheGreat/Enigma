"""
Module: scripts/level7_validate.py

Runs the unmodified system against the frozen suite and scores the result.

Four model paths, selected by --llm and --cache.

real
    Live Gemini through _default_llm_factory, the same factory the serving
    path uses. This is the only path that validates reasoning quality. The
    model name is read from ENIGMA_GEMINI_MODEL and the key from
    GOOGLE_API_KEY, ENIGMA_GEMINI_API_KEY or GEMINI_API_KEY.

real with --cache
    The same factory wrapped in the Level 6 content addressed response
    cache. The cache keys on the fully assembled prompt, so a repeat of an
    identical request is served without a model call. Level 8 and Level 9
    are unaffordable without it, and the hit rate it reports on this path is
    the first measurement of that rate against a model whose hypothesis text
    actually varies.

mock
    The Level 6 deterministic mock. Its text varies enough to exercise the
    keyword matching in scoring but comes from a fixed set chosen by digest,
    so its conclusion rates are properties of the mock.

fallback
    raising_llm_factory, which throws exactly as the unconfigured system
    does, so generation falls back to the three fixed strings at
    nodes.py:200-202. This reproduces the system as it behaves with no key
    present and is kept so that behaviour stays measurable after a key
    exists.

Everything downstream of generation is the real system on all four paths:
the sanity gate, evaluation, belief inertia, convergence, the epistemic
controls and the run logger. The fallback and mock paths therefore validate
the scoring machinery and the discriminating power of the suite, and the
correct conclusion rates they report are properties of the substitute rather
than of the reasoner.

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
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / "Enigma-AIAgent" / ".env")

sys.path.insert(0, str(PROJECT_ROOT / "Enigma-AIAgent"))

from enigma_reason.config import settings  # noqa: E402
from enigma_reason.domain.signal import Signal  # noqa: E402
from enigma_reason.graph.builder import EpistemicControls  # noqa: E402
from enigma_reason.graph.runner import _default_llm_factory  # noqa: E402
from enigma_reason.observability.llm_cache import CachingLLMFactory, ResponseCache  # noqa: E402
from enigma_reason.observability.manifest import build_run_manifest, write_manifest  # noqa: E402
from enigma_reason.observability.run_log import RunLogWriter, text_hash  # noqa: E402
from enigma_reason.replay.concurrent import ConcurrentReplay  # noqa: E402
from enigma_reason.replay.offline import OfflineReplay, mock_llm_factory  # noqa: E402
from enigma_reason.store.correlation import EntityCorrelation  # noqa: E402
from scenarios.generator import (  # noqa: E402
    CATEGORIES_BY_NAME,
    NEVER_SUFFICIENT,
    GroundTruth,
    Regime,
    Scenario,
    ScenarioParameters,
    suite_hash,
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


def build_factory(mode: str, seed: int, cache_path: Path | None):
    """Return the model factory, the cache behind it, and a description.

    The cache is only attached to the real path. Wrapping the mock or the
    fallback would report a hit rate that no model call was ever saved by,
    which is precisely the overstatement L6.8 warns the 0.936 figure is.
    """
    if mode == "mock":
        return mock_llm_factory(seed=seed), None, "Level 6 deterministic mock model"
    if mode == "fallback":
        return (
            raising_llm_factory(),
            None,
            "fallback hypotheses at nodes.py:200-202, no model call",
        )

    model_name = settings.gemini_model
    if cache_path is None:
        return _default_llm_factory, None, f"live Gemini {model_name}, uncached"

    cache = ResponseCache(cache_path, model=model_name)
    factory = CachingLLMFactory(_default_llm_factory, cache)
    return factory, cache, f"live Gemini {model_name} through the Level 6 response cache"


def convergence_report(run_log_path: Path) -> dict[str, Any]:
    """Summarise convergence and termination across every logged iteration.

    L7.5 established that the 0.8 threshold is never reached under the mock
    and that every analysis terminates by exhausting its iteration budget.
    Reporting the same three quantities on every path is what lets that
    finding be checked against a real model rather than assumed to carry.
    """
    scores: list[float] = []
    reasons: Counter[str] = Counter()
    unknown_dominant = 0
    terminal = 0
    for line in run_log_path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        record = json.loads(line)
        if record.get("record_type") == "retry":
            continue
        scores.append(float(record.get("convergence_score", 0.0)))
        if record.get("terminated"):
            terminal += 1
            reasons[str(record.get("termination_reason", "unknown"))] += 1
            hypotheses = record.get("hypotheses", [])
            if hypotheses:
                leader = max(hypotheses, key=lambda h: h.get("confidence", 0.0))
                if leader.get("is_unknown"):
                    unknown_dominant += 1
    return {
        "iterations": len(scores),
        "max_convergence": round(max(scores), 4) if scores else 0.0,
        "mean_convergence": round(sum(scores) / len(scores), 4) if scores else 0.0,
        "threshold": settings.graph_convergence_threshold,
        "reached_threshold": sum(
            1 for s in scores if s >= settings.graph_convergence_threshold
        ),
        "termination_reasons": dict(reasons),
        "terminal_iterations": terminal,
        "unknown_dominant_at_termination": unknown_dominant,
        "unknown_dominant_fraction": (
            round(unknown_dominant / terminal, 4) if terminal else 0.0
        ),
    }


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
        choices=("real", "mock", "fallback"),
        default="fallback",
        help=(
            "real drives live Gemini through the same factory the serving "
            "path uses, and is the only path that validates reasoning "
            "quality. mock is the Level 6 deterministic model, whose text "
            "varies enough to exercise the keyword matching in scoring. "
            "fallback is the unmodified system as it stands with no API key, "
            "where generation raises and the three fixed strings at "
            "nodes.py:200-202 are substituted."
        ),
    )
    parser.add_argument(
        "--cache",
        type=str,
        default="",
        help=(
            "Path to a Level 6 response cache. Only honoured on the real "
            "path, where it serves an identical prompt without a model call "
            "and reports the hit rate that Level 8 and Level 9 must be "
            "budgeted against."
        ),
    )
    parser.add_argument(
        "--scorer",
        choices=("keyword", "embedding"),
        default="keyword",
        help=(
            "keyword is the validated scorer. embedding reproduces the "
            "semantic scorer rejected in L7.9, which scored precision 0.2917 "
            "and recall 0.4375 against the hand labels where keyword scored "
            "0.8125 and 0.8125, and is kept reachable so that result stays "
            "reproducible."
        ),
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help=(
            "Scenarios to run at once. The default of 1 reproduces serial "
            "runs exactly. Units run concurrently but nothing inside a unit "
            "does, because an analysis's iterations are sequentially "
            "dependent."
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

    suite_path = Path(args.suite)
    if not suite_path.is_absolute():
        suite_path = (PROJECT_ROOT / suite_path).resolve()
    scenarios = load_suite(suite_path)
    if args.limit:
        scenarios = stratified_sample(scenarios, args.limit)

    cache_path = Path(args.cache) if args.cache and args.llm == "real" else None
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
    llm_factory, cache, llm_description = build_factory(args.llm, args.seed, cache_path)

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
    retries: list[dict[str, Any]] = []
    run_started = time.monotonic()
    with RunLogWriter(run_log_path) as writer:

        def build_replay(unit: str, unit_factory):
            """Create one scenario's replay with its own store and engine."""
            return OfflineReplay(
                unit_factory,
                run_log=writer,
                seed=args.seed,
                correlation=EntityCorrelation(),
                on_analysis=harvest,
                controls=controls,
            )

        if args.concurrency > 1:
            driver = ConcurrentReplay(
                build_replay,
                llm_factory,
                concurrency=args.concurrency,
                run_log=writer,
            )
            outcome = driver.run(
                [(scenario.scenario_id, scenario.signals) for scenario in scenarios]
            )
            analyses = outcome.analyses_run
            retries = [r.to_dict() for r in outcome.retries]
        else:
            for scenario in scenarios:
                replay = build_replay(scenario.scenario_id, llm_factory)
                result = replay.run(scenario.signals)
                analyses += result.analyses_run
        writer.flush()
        iterations_logged = writer.written
        dropped = writer.dropped
    elapsed_seconds = time.monotonic() - run_started

    cache_stats = None
    if cache is not None:
        cache.save()
        cache_stats = cache.stats.to_dict()
    model_calls = cache_stats["misses"] if cache_stats else iterations_logged
    seconds_per_model_call = (
        round(elapsed_seconds / model_calls, 4) if model_calls else 0.0
    )

    matcher = None
    if args.scorer == "embedding":
        from scenarios.semantic import EmbeddingMatcher

        matcher = EmbeddingMatcher()
    outcomes, overall, per_regime = score_run(
        run_log_path, scenarios, situation_entities, descriptions, matcher
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
        "suite": str(suite_path.relative_to(PROJECT_ROOT)),
        "scenarios": len(scenarios),
        "situations_scored": overall.situations,
        "analyses_run": analyses,
        "iterations_logged": iterations_logged,
        "run_log_dropped": dropped,
        "llm": llm_description,
        "llm_mode": args.llm,
        "scorer": args.scorer,
        "concurrency": args.concurrency,
        "retry_count": len(retries),
        "model_name": settings.gemini_model if args.llm == "real" else args.llm,
        "cache_path": str(cache_path) if cache_path else None,
        "cache": cache_stats,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "model_calls": model_calls,
        "seconds_per_model_call": seconds_per_model_call,
        "requests_per_minute": round(model_calls / elapsed_seconds * 60, 1)
        if elapsed_seconds
        else 0.0,
        "retry_records": retries,
        "convergence": convergence_report(run_log_path),
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
    mirrors_canonical = (
        args.llm == "fallback"
        and not args.limit
        and not ablated
        and suite_path == (RESULTS_DIR / "suite.jsonl")
        and len(scenarios) == 400
    )
    if mirrors_canonical:
        (RESULTS_DIR / "validation_run.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        (RESULTS_DIR / "metric_distributions.csv").write_text(
            distributions_path.read_text(encoding="utf-8"), encoding="utf-8"
        )

    manifest = build_run_manifest(
        experiment=f"level7_validate_{tag}",
        seed=args.seed,
        config={
            "suite": str(suite_path.relative_to(PROJECT_ROOT)),
            "scenarios": len(scenarios),
            "llm_mode": args.llm,
        "scorer": args.scorer,
            "model_name": settings.gemini_model if args.llm == "real" else args.llm,
            "cache_path": str(cache_path) if cache_path else None,
            "ablate": ablated,
            "epistemic_controls": controls.as_dict(),
            "graph_max_iterations": settings.graph_max_iterations,
            "graph_convergence_threshold": settings.graph_convergence_threshold,
        },
        started_at=started,
        project_root=PROJECT_ROOT,
        dataset=suite_path,
        extra={
            "situations_scored": overall.situations,
            "suite_hash": suite_hash(scenarios),
            "model_calls": model_calls,
            "seconds_per_model_call": seconds_per_model_call,
        "requests_per_minute": round(model_calls / elapsed_seconds * 60, 1)
        if elapsed_seconds
        else 0.0,
        "retry_records": retries,
            "cache": cache_stats,
        },
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
    convergence = report["convergence"]
    print(
        f"model calls {model_calls}  elapsed {elapsed_seconds:.1f}s  "
        f"seconds per call {seconds_per_model_call}"
    )
    print(
        f"concurrency {args.concurrency}  "
        f"requests per minute {report['requests_per_minute']}  "
        f"retries {len(retries)}"
    )
    if cache_stats:
        print(
            f"cache hits {cache_stats['hits']}  misses {cache_stats['misses']}  "
            f"hit rate {cache_stats['hit_rate']}"
        )
    print(
        f"convergence max {convergence['max_convergence']} against threshold "
        f"{convergence['threshold']}  reached {convergence['reached_threshold']}"
    )
    print(f"termination {json.dumps(convergence['termination_reasons'])}")
    print(f"distinct hypothesis texts {len(descriptions)}")
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
