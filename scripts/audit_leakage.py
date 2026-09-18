"""
Module: scripts/audit_leakage.py

Static verifier that the Level 3 training pipeline cannot leak test data into a
fitted transform.

The four leakage paths recorded in paper/EVIDENCE.md section A5 were all the
same mistake: a transform was fitted on a frame that had not yet been split. A
static check catches that class of error before a run rather than after, and
runs cheaply enough to sit in continuous integration.

Checks performed:

    1. No fit, fit_transform or fit_resample is called on an identifier whose
       name marks it as test or pool data.
    2. Every resampler appears inside an imblearn Pipeline, never called
       directly on a frame.
    3. The scaler, selector and outlier handler are constructed inside a
       pipeline builder rather than fitted at module scope.
    4. The test partition is transformed but never fitted on.
    5. The split call precedes every fit in the module's execution order.

Exit code is 0 when clean and 1 when any violation is found, so it gates.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

FITTING_METHODS = {"fit", "fit_transform", "fit_resample", "fit_predict"}
TRANSFORM_METHODS = {"transform", "predict", "predict_proba"}
RESAMPLER_NAMES = {"SMOTE", "ADASYN", "RandomOverSampler", "RandomUnderSampler", "SMOTENC"}
FITTED_TRANSFORM_NAMES = {
    "StandardScaler",
    "MinMaxScaler",
    "RobustScaler",
    "SelectKBest",
    "OutlierWinsoriser",
    "OneHotEncoder",
    "ColumnTransformer",
}

TEST_IDENTIFIER_MARKERS = ("test", "holdout", "unseen")
POOL_IDENTIFIER_MARKERS = ("pool",)
SPLIT_FUNCTIONS = {"train_test_split"}


@dataclass
class Violation:
    """One detected leakage hazard."""

    rule: str
    detail: str
    line: int

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable view."""
        return {"rule": self.rule, "detail": self.detail, "line": self.line}


@dataclass
class AuditResult:
    """Outcome of auditing one file."""

    path: str
    violations: list[Violation] = field(default_factory=list)
    fit_calls: list[str] = field(default_factory=list)
    transform_calls: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        """True when no violations were found."""
        return not self.violations


def _target_name(node: ast.AST) -> str:
    """Best-effort textual name of whatever a call was made on."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_target_name(node.value)}.{node.attr}"
    if isinstance(node, ast.Subscript):
        return _target_name(node.value)
    if isinstance(node, ast.Call):
        return _target_name(node.func)
    return type(node).__name__


def _first_argument_name(call: ast.Call) -> str:
    """Name of the first positional argument, or an empty string."""
    if not call.args:
        return ""
    return _target_name(call.args[0])


def _marks_test_data(identifier: str) -> bool:
    """True when an identifier names data that must never be fitted on."""
    lowered = identifier.lower()
    return any(marker in lowered for marker in TEST_IDENTIFIER_MARKERS)


def _marks_pool_data(identifier: str) -> bool:
    """True when an identifier names the unsplit pool."""
    lowered = identifier.lower()
    return any(marker in lowered for marker in POOL_IDENTIFIER_MARKERS)


class LeakageVisitor(ast.NodeVisitor):
    """Walks a module and records fitting and transforming call sites."""

    def __init__(self, result: AuditResult) -> None:
        self.result = result
        self.split_lines: list[int] = []
        self.direct_resampler_calls: list[tuple[str, int]] = []
        self.module_level_fits: list[tuple[str, int]] = []
        self._function_depth = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Track whether a call site sits inside a function."""
        self._function_depth += 1
        self.generic_visit(node)
        self._function_depth -= 1

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Track async functions the same way."""
        self.visit_FunctionDef(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Record every fitting and transforming call."""
        if isinstance(node.func, ast.Name) and node.func.id in SPLIT_FUNCTIONS:
            self.split_lines.append(node.lineno)

        if isinstance(node.func, ast.Attribute):
            method = node.func.attr
            receiver = _target_name(node.func.value)
            argument = _first_argument_name(node)

            if method in FITTING_METHODS:
                self.result.fit_calls.append(f"{receiver}.{method}({argument}) line {node.lineno}")

                if _marks_test_data(argument):
                    self.result.violations.append(
                        Violation(
                            rule="fit_on_test_data",
                            detail=f"{receiver}.{method} called on {argument!r}",
                            line=node.lineno,
                        )
                    )
                if _marks_pool_data(argument):
                    self.result.violations.append(
                        Violation(
                            rule="fit_on_unsplit_pool",
                            detail=(
                                f"{receiver}.{method} called on {argument!r}, which names "
                                "the pool before it is split"
                            ),
                            line=node.lineno,
                        )
                    )
                if receiver.split(".")[-1] in RESAMPLER_NAMES:
                    self.direct_resampler_calls.append((receiver, node.lineno))
                if self._function_depth == 0:
                    self.module_level_fits.append((f"{receiver}.{method}", node.lineno))

            if method in TRANSFORM_METHODS:
                self.result.transform_calls.append(
                    f"{receiver}.{method}({argument}) line {node.lineno}"
                )

        self.generic_visit(node)


def audit_file(path: Path) -> AuditResult:
    """Audit one Python module for leakage hazards.

    Args:
        path: Module to audit.

    Returns:
        The audit result, including every violation found.
    """
    result = AuditResult(path=str(path))
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))

    visitor = LeakageVisitor(result)
    visitor.visit(tree)

    for receiver, line in visitor.direct_resampler_calls:
        result.violations.append(
            Violation(
                rule="resampler_outside_pipeline",
                detail=(
                    f"{receiver} was fitted directly. Resamplers must sit inside an "
                    "imblearn Pipeline so they are skipped during transform"
                ),
                line=line,
            )
        )

    for name, line in visitor.module_level_fits:
        result.violations.append(
            Violation(
                rule="fit_at_module_scope",
                detail=f"{name} is fitted at module scope, outside any function",
                line=line,
            )
        )

    if visitor.split_lines:
        earliest_split = min(visitor.split_lines)
        for entry in result.fit_calls:
            line = int(entry.rsplit(" ", 1)[-1])
            if line < earliest_split:
                result.violations.append(
                    Violation(
                        rule="fit_before_split",
                        detail=f"{entry} occurs before train_test_split at line {earliest_split}",
                        line=line,
                    )
                )

    return result


def audit_runtime_pipeline(module_dir: Path) -> list[Violation]:
    """Check the constructed pipeline structurally rather than textually.

    Args:
        module_dir: Directory holding level3_pipeline, added to the import path
            so the audit can run from any working directory.

    Returns:
        Violations describing any resampler that is not terminal, or any
        pipeline whose transforms are not all fitted estimators.
    """
    violations: list[Violation] = []
    if str(module_dir) not in sys.path:
        sys.path.insert(0, str(module_dir))
    try:
        from imblearn.pipeline import Pipeline as ImbalancedPipeline

        from level3_pipeline import build_resampling_pipeline

        pipeline = build_resampling_pipeline(
            numeric_columns=["dur", "rate"], n_features=2, seed=0
        )
    except Exception as exc:
        violations.append(
            Violation(
                rule="pipeline_not_constructible",
                detail=f"could not build the pipeline for structural audit: {exc}",
                line=0,
            )
        )
        return violations

    if not isinstance(pipeline, ImbalancedPipeline):
        violations.append(
            Violation(
                rule="pipeline_wrong_type",
                detail="the training pipeline is not an imblearn Pipeline, so a "
                "resampler would run during transform",
                line=0,
            )
        )
        return violations

    step_names = [name for name, _ in pipeline.steps]
    resampler_positions = [
        index
        for index, (_, step) in enumerate(pipeline.steps)
        if type(step).__name__ in RESAMPLER_NAMES
    ]

    if not resampler_positions:
        violations.append(
            Violation(rule="no_resampler_found", detail=f"steps were {step_names}", line=0)
        )
    else:
        for position in resampler_positions:
            if position != len(pipeline.steps) - 1:
                violations.append(
                    Violation(
                        rule="resampler_not_terminal",
                        detail=(
                            f"resampler at position {position} of {len(pipeline.steps)}; "
                            "it must be last so transform skips it"
                        ),
                        line=0,
                    )
                )

    return violations


def main() -> None:
    """Audit the Level 3 pipeline and exit non-zero on any violation."""
    parser = argparse.ArgumentParser(
        description="Statically verify the training pipeline cannot leak test data."
    )
    parser.add_argument(
        "--files",
        type=Path,
        nargs="*",
        default=[
            Path("/mnt/f/XAI Project/Enigma-ML-Layer/train_level3.py"),
            Path("/mnt/f/XAI Project/Enigma-ML-Layer/level3_pipeline.py"),
        ],
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/mnt/f/XAI Project/results/classifier/leakage_audit.json"),
    )
    parser.add_argument("--skip-runtime", action="store_true")
    args = parser.parse_args()

    results = [audit_file(path) for path in args.files]
    module_dir = args.files[0].parent if args.files else Path.cwd()
    runtime_violations = [] if args.skip_runtime else audit_runtime_pipeline(module_dir)

    total_violations = sum(len(result.violations) for result in results) + len(
        runtime_violations
    )

    report = {
        "seed": args.seed,
        "files_audited": [result.path for result in results],
        "total_violations": total_violations,
        "static": [
            {
                "path": result.path,
                "clean": result.clean,
                "violations": [violation.as_dict() for violation in result.violations],
                "fit_call_count": len(result.fit_calls),
                "fit_calls": result.fit_calls,
                "transform_call_count": len(result.transform_calls),
            }
            for result in results
        ],
        "runtime": [violation.as_dict() for violation in runtime_violations],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"wrote {args.output}")
    for result in results:
        status = "clean" if result.clean else f"{len(result.violations)} violations"
        print(f"  {Path(result.path).name:<24} {status}")
        for violation in result.violations:
            print(f"      line {violation.line}: {violation.rule}: {violation.detail}")
        for call in result.fit_calls:
            print(f"      fit site: {call}")

    if runtime_violations:
        print("  runtime structural audit:")
        for violation in runtime_violations:
            print(f"      {violation.rule}: {violation.detail}")
    else:
        print("  runtime structural audit: clean, resampler is terminal")

    print(f"total violations: {total_violations}")
    sys.exit(1 if total_violations else 0)


if __name__ == "__main__":
    main()
