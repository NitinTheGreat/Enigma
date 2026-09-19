#!/usr/bin/env bash
set -euo pipefail
cd "/mnt/f/XAI Project"
export CUDA_VISIBLE_DEVICES=-1
/opt/enigma/.venv-agent/bin/python - <<'PY' 2>/dev/null
import sys
from pathlib import Path

sys.path.insert(0, "Enigma-AIAgent")
sys.path.insert(0, "scripts")

from scenarios.generator import suite_hash
from level7_validate import load_suite, stratified_sample

FROZEN = "52b89293b37baff655f97a41a42b67962059c2c96c5a34a716c69af7202f0efc"

full = load_suite(Path("results/scenarios/suite.jsonl"))
slice_ = stratified_sample(full, 4)
sub = load_suite(Path("results/scenarios/sub_suite.jsonl"))

print("parent suite hash   ", suite_hash(full))
print("frozen L7.1 hash    ", FROZEN)
print("parent matches L7.1 ", suite_hash(full) == FROZEN)
print()
print("real run slice hash ", suite_hash(slice_))
print("real run scenarios  ", [s.scenario_id for s in slice_])
print("real run regimes    ", [s.ground_truth.regime.value for s in slice_])
print()
print("sub suite hash      ", suite_hash(sub))
print("sub suite scenarios ", len(sub))
PY
