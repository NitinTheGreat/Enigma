"""
Module: scripts/build_demo_data.py

Builds the data the reviewer demo shows, from committed result files only.

Every number written here is copied from a file that is in the repository,
and every number carries the path of that file and the field it came from,
so a reviewer who asks where a figure comes from can be shown the file. No
value is typed in. The one exception the demo needs, the four reasoning
traces, comes from results/demo/traces_seed42_t080.json, a committed extract
written by scripts/extract_demo_traces.py from the local run log.

Before writing anything the script checks the paper's headline numbers
against what it has read, and stops if any differs. The tolerance is 5e-4,
or half a unit of the last digit the paper states where the paper rounds to
fewer places, so 0.22 is checked to within 0.005 and 0.1818 to within 5e-4.
If a value cannot be found at all, the script names it and stops.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from statistics import mean
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS = PROJECT_ROOT / "results"
OUT_DIR = PROJECT_ROOT / "demo" / "public" / "data"
NODES = PROJECT_ROOT / "Enigma-AIAgent" / "enigma_reason" / "graph" / "nodes.py"
CONFIG = PROJECT_ROOT / "Enigma-AIAgent" / "enigma_reason" / "config.py"

THRESHOLD = 0.80
BASE_TOLERANCE = 5e-4
SWITCHES = ("U", "S", "A", "P")
REGIMES = ("clear", "ambiguous", "sparse", "unknown_attack")
SEEDS = (42, 123, 456, 789, 1024)


class MissingValue(Exception):
    """A value the demo needs is absent from the committed results."""


def rel(path: Path) -> str:
    """Return a repository relative path with forward slashes."""
    return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")


def committed(path: Path) -> Path:
    """Refuse to read a file that does not exist."""
    if not path.is_file():
        raise MissingValue("file absent: %s" % rel(path))
    return path


def sourced(value: Any, path: Path, field: str) -> dict[str, Any]:
    """Wrap a value with the file and field it was read from."""
    return {"value": value, "source": rel(path), "field": field}


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a committed CSV."""
    with committed(path).open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> Any:
    """Read a committed JSON file."""
    return json.loads(committed(path).read_text(encoding="utf-8"))


def same(a: float, b: float) -> bool:
    """Compare two floats as written in a results file."""
    return abs(float(a) - float(b)) < 1e-9


def build_verdicts() -> dict[str, Any]:
    """Assemble Table I of the paper from the files that measure it."""
    effects_path = RESULTS / "ablation" / "main_effects_seed42.csv"
    two_level_path = RESULTS / "two_level" / "two_level_seed42.json"
    isolation_path = RESULTS / "convergence_isolation" / "isolation_seed42.json"
    rows = read_csv(effects_path)

    def effect(switch: str) -> dict[str, Any]:
        for r in rows:
            if (r["switch"] == switch and r["metric"] == "abstention_rate"
                    and same(r["convergence_threshold"], THRESHOLD)):
                return {
                    "effect": sourced(round(float(r["effect_mean"]), 4), effects_path,
                                      "switch=%s metric=abstention_rate threshold=0.8 effect_mean" % switch),
                    "sd": sourced(round(float(r["effect_sd"]), 4), effects_path, "effect_sd"),
                }
        raise MissingValue("main effect of %s on abstention at 0.80" % switch)

    two_level = read_json(two_level_path)
    isolation = read_json(isolation_path)
    for key in ("sensor_effect_with_epistemic_on", "sensor_effect_with_epistemic_off",
                "abstained_signal_fraction_overall"):
        if key not in two_level:
            raise MissingValue("%s in %s" % (key, rel(two_level_path)))
    if "inertia_effect_on_convergence" not in isolation:
        raise MissingValue("inertia_effect_on_convergence in %s" % rel(isolation_path))

    mechanisms = [
        {"key": "U", "name": "UNKNOWN hypothesis", "verdict": "works", "wired": True,
         "plain": "Keeps 'I do not know' on the table, so the AI can decline.", **effect("U")},
        {"key": "S", "name": "Sanity gate", "verdict": "works, overlaps U", "wired": True,
         "plain": "Adds doubt when the evidence is thin.", **effect("S")},
        {"key": "A", "name": "Asymmetric decay", "verdict": "inert", "wired": True,
         "plain": "Lets doubt grow faster than belief. Measured effect is within the noise.",
         **effect("A")},
        {"key": "P", "name": "Persistence", "verdict": "not connected", "wired": False,
         "plain": "Should wait for an idea to lead twice. No idea ever survives a round, so it never fires.",
         **effect("P")},
        {"key": "flag", "name": "Sensor unsure flag", "verdict": "not connected", "wired": False,
         "plain": "The sensor marks signals it is unsure about. No step ever reads the mark.",
         "effect": sourced(two_level["sensor_effect_with_epistemic_on"], two_level_path,
                           "sensor_effect_with_epistemic_on"),
         "effect_guardrails_off": sourced(two_level["sensor_effect_with_epistemic_off"], two_level_path,
                                          "sensor_effect_with_epistemic_off")},
        {"key": "inertia", "name": "Belief inertia", "verdict": "no effect on convergence", "wired": True,
         "plain": "Limits how far a belief can move in one round.",
         "effect": sourced(isolation["inertia_effect_on_convergence"], isolation_path,
                           "inertia_effect_on_convergence")},
    ]
    return {
        "verdict_text_source": "paper/enigma-paper/main.tex, Table I",
        "threshold": THRESHOLD,
        "metric": "abstention rate, guardrail removed minus guardrail kept, five seeds",
        "mechanisms": mechanisms,
    }


def build_configurations() -> dict[str, Any]:
    """Return abstention and premature convergence for all sixteen configurations."""
    cells_path = RESULTS / "ablation" / "cells_detail_seed42.json"
    cells = read_json(cells_path)
    names = ["allon"] + ["".join(c) for n in range(1, 5)
                         for c in __import__("itertools").combinations(SWITCHES, n)]
    configurations = []
    for name in names:
        rows = [c for c in cells if c["configuration"] == name and same(c["convergence_threshold"], THRESHOLD)]
        if len(rows) != len(SEEDS):
            raise MissingValue("configuration %s at 0.80 has %d seeds, expected %d"
                               % (name, len(rows), len(SEEDS)))
        ablated = "" if name == "allon" else name
        entry: dict[str, Any] = {
            "configuration": name,
            "removed": list(ablated),
            "kept": [s for s in SWITCHES if s not in ablated],
            "seeds": len(rows),
            "overall": {
                "abstention_rate": sourced(round(mean(r["abstention_rate"] for r in rows), 4), cells_path,
                                           "configuration=%s threshold=0.8 abstention_rate, mean of 5 seeds" % name),
                "premature_convergence_rate": sourced(
                    round(mean(r["premature_convergence_rate"] for r in rows), 4), cells_path,
                    "configuration=%s threshold=0.8 premature_convergence_rate, mean of 5 seeds" % name),
            },
            "per_regime": {},
        }
        for regime in REGIMES:
            entry["per_regime"][regime] = {
                "abstention_rate": sourced(
                    round(mean(r["per_regime"][regime]["abstention_rate"] for r in rows), 4), cells_path,
                    "configuration=%s per_regime.%s.abstention_rate, mean of 5 seeds" % (name, regime)),
                "premature_convergence_rate": sourced(
                    round(mean(r["per_regime"][regime]["premature_convergence_rate"] for r in rows), 4),
                    cells_path,
                    "configuration=%s per_regime.%s.premature_convergence_rate, mean of 5 seeds" % (name, regime)),
            }
        configurations.append(entry)
    return {"threshold": THRESHOLD, "configurations": configurations}


def build_regime_effects() -> dict[str, Any]:
    """Return the main effects of U and S on sparse and unknown attack cases."""
    path = RESULTS / "ablation" / "regime_effects_seed42.csv"
    rows = read_csv(path)
    out: dict[str, Any] = {"threshold": THRESHOLD, "metric": "abstention_rate", "effects": {}}
    for switch in ("U", "S"):
        out["effects"][switch] = {}
        for regime in REGIMES:
            match = [r for r in rows if r["switch"] == switch and r["regime"] == regime
                     and r["metric"] == "abstention_rate" and same(r["convergence_threshold"], THRESHOLD)]
            if not match:
                raise MissingValue("regime effect %s %s" % (switch, regime))
            out["effects"][switch][regime] = {
                "effect": sourced(round(float(match[0]["effect_mean"]), 4), path,
                                  "switch=%s regime=%s metric=abstention_rate effect_mean" % (switch, regime)),
                "sd": sourced(round(float(match[0]["effect_sd"]), 4), path, "effect_sd"),
            }
    return out


def build_clock() -> dict[str, Any]:
    """Return the clock study for the three modes."""
    path = RESULTS / "clock_study" / "study_seed42.json"
    study = read_json(path)
    modes = {}
    for summary in study["summaries"]:
        mode = summary["clock_mode"]
        cells = [c for c in study["cells"] if c["clock_mode"] == mode]
        if len(cells) != len(SEEDS):
            raise MissingValue("clock mode %s has %d seeds" % (mode, len(cells)))
        modes[mode] = {
            "quiet_fraction": sourced(summary["quiet_fraction_mean"], path,
                                      "summaries[%s].quiet_fraction_mean" % mode),
            "abstention_rate": sourced(summary["abstention_rate_mean"], path,
                                       "summaries[%s].abstention_rate_mean" % mode),
            "correct_conclusion_rate": sourced(summary["correct_conclusion_rate_mean"], path,
                                               "summaries[%s].correct_conclusion_rate_mean" % mode),
            "clear_regime_correct_rate": sourced(
                round(mean(c["per_regime"]["clear"]["correct_conclusion_rate"] for c in cells), 4), path,
                "cells[clock_mode=%s].per_regime.clear.correct_conclusion_rate, mean of 5 seeds" % mode),
            "trend_labels_seen": sourced(summary["trend_labels_seen_mean"], path,
                                         "summaries[%s].trend_labels_seen_mean" % mode),
        }
    for needed in ("conflated", "wall", "separated"):
        if needed not in modes:
            raise MissingValue("clock mode %s" % needed)
    return {"bug_off": "separated", "bug_on": "conflated", "modes": modes}


def build_repair() -> dict[str, Any]:
    """Return the repair against the baseline at threshold 0.30."""
    path = RESULTS / "repair" / "repair_summary_seed42.csv"
    rows = [r for r in read_csv(path) if same(r["convergence_threshold"], 0.30)]
    if not rows:
        raise MissingValue("repair summary at threshold 0.30")
    r = rows[0]
    out: dict[str, Any] = {"threshold": 0.30}
    for arm in ("baseline", "repair"):
        out[arm] = {
            "recurrence": sourced(float(r[arm + "_recurrence_rate_mean"]), path, arm + "_recurrence_rate_mean"),
            "convergence_fraction": sourced(float(r[arm + "_convergence_fraction_mean"]), path,
                                            arm + "_convergence_fraction_mean"),
            "max_convergence": sourced(float(r[arm + "_max_convergence_mean"]), path, arm + "_max_convergence_mean"),
            "max_dominant_iterations": sourced(float(r[arm + "_max_dominant_iterations_mean"]), path,
                                               arm + "_max_dominant_iterations_mean"),
        }
    return out


def build_sensor() -> dict[str, Any]:
    """Return accuracy, macro F1, false positive rate and unknown attack AUROC."""
    comparison_path = RESULTS / "baselines" / "classifier_comparison.json"
    level4_path = RESULTS / "calibration" / "level4_summary.json"
    comparison = read_json(comparison_path)["comparison"]
    level4 = read_json(level4_path)
    try:
        mlp_auroc = level4["configs"]["openset"]["separation"]["auroc"]["negative_calibrated_confidence"]
    except KeyError as missing:
        raise MissingValue("MLP unknown attack AUROC in %s" % rel(level4_path)) from missing

    def tree_auroc(model: str) -> dict[str, Any]:
        values = []
        for seed in SEEDS:
            path = RESULTS / "baselines" / ("%s_openset_seed%d.json" % (model, seed))
            data = read_json(path)
            values.append(data["separation"]["auroc_negative_calibrated_probability"])
        return {"value": round(mean(values), 4),
                "source": "results/baselines/%s_openset_seed{42,123,456,789,1024}.json" % model,
                "field": "separation.auroc_negative_calibrated_probability, mean of 5 seeds"}

    models = []
    for key, label, auroc in (
        ("mlp", "Neural network, five seeds", sourced(round(mlp_auroc, 4), level4_path,
                                                      "configs.openset.separation.auroc.negative_calibrated_confidence, "
                                                      "five member ensemble")),
        ("rf", "Random Forest", tree_auroc("rf")),
        ("xgb", "XGBoost", tree_auroc("xgb")),
    ):
        if key not in comparison:
            raise MissingValue("classifier %s in %s" % (key, rel(comparison_path)))
        c = comparison[key]
        models.append({
            "key": key, "label": label,
            "accuracy": sourced(round(c["accuracy"]["mean"], 4), comparison_path,
                                "comparison.%s.accuracy.mean, closed set, natural distribution" % key),
            "macro_f1": sourced(round(c["macro_f1"]["mean"], 4), comparison_path, "comparison.%s.macro_f1.mean" % key),
            "false_positive_rate": sourced(round(c["false_positive_rate"]["mean"], 4), comparison_path,
                                           "comparison.%s.false_positive_rate.mean, normal flagged as attack" % key),
            "unknown_attack_auroc": auroc,
        })
    return {"models": models}


def build_system() -> dict[str, Any]:
    """Return the numbers shown on the pipeline diagram."""
    manifest_path = RESULTS / "scenarios" / "sub_suite_manifest.json"
    manifest = read_json(manifest_path)
    source = committed(NODES).read_text(encoding="utf-8")
    block = source.split("def assemble_context", 1)[1].split("return {\"context\"", 1)[0]
    fields = re.findall(r'^\s+"([a-z_]+)":', block, flags=re.M)
    if len(fields) != 10:
        raise MissingValue("expected ten context fields in assemble_context, found %d" % len(fields))
    return {
        "scenarios": sourced(manifest["scenario_count"], manifest_path, "scenario_count"),
        "signals": sourced(manifest["signal_count"], manifest_path, "signal_count"),
        "situations": sourced(manifest["situation_count_under_entity_grouping"], manifest_path,
                              "situation_count_under_entity_grouping"),
        "sensor_unsure_fraction": sourced(manifest["abstained_signal_fraction"], manifest_path,
                                          "abstained_signal_fraction"),
        "suite_hash": sourced(manifest["sub_suite_hash"][:8], manifest_path, "sub_suite_hash"),
        "barrier_fields": {"value": fields, "source": rel(NODES), "field": "assemble_context return value"},
        "max_rounds": {"value": max_rounds(), "source": rel(CONFIG),
                       "field": "graph_max_iterations default"},
    }


def max_rounds() -> int:
    """Read the reasoning loop's iteration cap from the agent's settings."""
    found = re.search(r"graph_max_iterations: int = (\d+)", committed(CONFIG).read_text(encoding="utf-8"))
    if not found:
        raise MissingValue("graph_max_iterations in %s" % rel(CONFIG))
    return int(found.group(1))


def build_traces() -> dict[str, Any]:
    """Return the four committed traces, with their source."""
    path = RESULTS / "demo" / "traces_seed42_t080.json"
    data = read_json(path)
    data["source"] = rel(path)
    return data


def config_value(configurations: dict[str, Any], name: str, field: str = "abstention_rate") -> float:
    """Return one overall value for a configuration."""
    for c in configurations["configurations"]:
        if c["configuration"] == name:
            return c["overall"][field]["value"]
    raise MissingValue("configuration %s" % name)


def validate(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Check the paper's headline numbers against what was read."""
    v = {m["key"]: m for m in data["verdicts"]["mechanisms"]}
    cfg = data["configurations"]
    eff = data["regime_effects"]["effects"]
    clock = data["clock"]["modes"]
    rep = data["repair"]

    def u_off_all_zero() -> float:
        return max(c["overall"]["abstention_rate"]["value"] for c in cfg["configurations"] if "U" in c["removed"])

    checks = [
        ("Table I, U", v["U"]["effect"]["value"], -0.0985, 4),
        ("Table I, S", v["S"]["effect"]["value"], -0.0833, 4),
        ("Table I, A", v["A"]["effect"]["value"], -0.0030, 4),
        ("Table I, P", v["P"]["effect"]["value"], 0.0000, 4),
        ("Table I, sensor flag, guardrails on", v["flag"]["effect"]["value"], 0.000000, 6),
        ("Table I, sensor flag, guardrails off", v["flag"]["effect_guardrails_off"]["value"], 0.000000, 6),
        ("Table II, all on", config_value(cfg, "allon"), 0.1818, 4),
        ("Table II, minus S", config_value(cfg, "S"), 0.0212, 4),
        ("Table II, minus SA", config_value(cfg, "SA"), 0.0091, 4),
        ("Table II, every config with U off", u_off_all_zero(), 0.0000, 4),
        ("Finding 3, sparse U", eff["U"]["sparse"]["effect"]["value"], -0.5500, 4),
        ("Finding 3, sparse S", eff["S"]["sparse"]["effect"]["value"], -0.4500, 4),
        ("Finding 3, unknown attack U", eff["U"]["unknown_attack"]["effect"]["value"], -0.0063, 4),
        ("Clock, abstention bug off", clock["separated"]["abstention_rate"]["value"], 0.1818, 4),
        ("Clock, abstention bug on", clock["conflated"]["abstention_rate"]["value"], 0.5273, 4),
        ("Clock, correct bug off", clock["separated"]["correct_conclusion_rate"]["value"], 0.22, 2),
        ("Clock, correct bug on", clock["conflated"]["correct_conclusion_rate"]["value"], 0.50, 2),
        ("Clock, clear bug off", clock["separated"]["clear_regime_correct_rate"]["value"], 0.130, 3),
        ("Clock, clear bug on", clock["conflated"]["clear_regime_correct_rate"]["value"], 0.080, 3),
        ("Clock, quiet bug on", clock["conflated"]["quiet_fraction"]["value"], 1.00, 2),
        ("Repair, recurrence baseline", rep["baseline"]["recurrence"]["value"], 0.0, 4),
        ("Repair, recurrence repaired", rep["repair"]["recurrence"]["value"], 0.2045, 4),
        ("Repair, convergence baseline", rep["baseline"]["convergence_fraction"]["value"], 0.0, 4),
        ("Repair, convergence repaired", rep["repair"]["convergence_fraction"]["value"], 0.1551, 4),
        ("Repair, max score baseline", rep["baseline"]["max_convergence"]["value"], 0.2900, 4),
        ("Repair, max score repaired", rep["repair"]["max_convergence"]["value"], 0.4530, 4),
    ]
    results = []
    for name, actual, expected, places in checks:
        tolerance = max(BASE_TOLERANCE, 0.5 * 10 ** (-places))
        results.append({"check": name, "expected": expected, "actual": actual,
                        "tolerance": tolerance, "passes": abs(actual - expected) <= tolerance})
    unknown_trace = next(t for t in data["traces"]["traces"] if t["regime"] == "unknown_attack")
    results.append({"check": "Trace, unknown attack is the paper's Figure 3 situation",
                    "expected": "09e0a866", "actual": unknown_trace["situation_id"][:8],
                    "tolerance": 0, "passes": unknown_trace["situation_id"].startswith("09e0a866")})
    return results


def main() -> int:
    """Read, validate, and write the demo data."""
    parser = argparse.ArgumentParser(description="Build the demo data from committed results.")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    try:
        data = {
            "verdicts": build_verdicts(),
            "configurations": build_configurations(),
            "regime_effects": build_regime_effects(),
            "clock": build_clock(),
            "repair": build_repair(),
            "sensor": build_sensor(),
            "system": build_system(),
            "traces": build_traces(),
        }
    except MissingValue as missing:
        print("STOPPED: a value the demo needs is not in the committed results")
        print("  %s" % missing)
        return 2

    checks = validate(data)
    print("seed %d   threshold %.2f" % (args.seed, THRESHOLD))
    print("")
    print("%-52s %10s %10s  %s" % ("validation against the paper", "expected", "actual", ""))
    for c in checks:
        exp = c["expected"] if isinstance(c["expected"], str) else "%+.6f" % c["expected"] if "flag" in c["check"] else "%+.4f" % c["expected"]
        act = c["actual"] if isinstance(c["actual"], str) else "%+.6f" % c["actual"] if "flag" in c["check"] else "%+.4f" % c["actual"]
        print("%-52s %10s %10s  %s" % (c["check"], exp, act, "ok" if c["passes"] else "MISMATCH"))
    failed = [c for c in checks if not c["passes"]]
    if failed:
        print("")
        print("STOPPED: %d value(s) disagree with the paper; nothing written" % len(failed))
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, payload in data.items():
        payload = dict(payload)
        payload["seed"] = args.seed
        (OUT_DIR / (name + ".json")).write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                                                encoding="utf-8")
    (OUT_DIR / "validation.json").write_text(json.dumps(
        {"seed": args.seed, "checks": checks, "all_pass": True}, indent=1), encoding="utf-8")
    print("")
    print("ALL %d CHECKS PASS" % len(checks))
    for name in list(data) + ["validation"]:
        path = OUT_DIR / (name + ".json")
        print("  written %-40s %6.1f KB" % (rel(path), path.stat().st_size / 1024))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
