#!/usr/bin/env bash
set -euo pipefail
cd "/mnt/f/XAI Project"
export CUDA_VISIBLE_DEVICES=-1
rm -f results/budget/throughput_cache_seed42.json
/opt/enigma/.venv-agent/bin/python scripts/level7_validate.py \
  --seed 42 \
  --llm real \
  --concurrency "${1:-25}" \
  --suite results/scenarios/sub_suite.jsonl \
  --limit "${2:-8}" \
  --cache results/budget/throughput_cache_seed42.json \
  --tag "conc${1:-25}" \
  > /tmp/l8_tp.out 2>/tmp/l8_tp.err
grep -E "^seed |^scenarios |^model calls|^concurrency |^cache hits|^convergence max" /tmp/l8_tp.out
