#!/usr/bin/env bash
set -euo pipefail
cd "/mnt/f/XAI Project"
export CUDA_VISIBLE_DEVICES=-1
for f in conflated_42 conflated_123 conflated_456 conflated_789 conflated_1024 wall_42; do
  p="results/clock_study/${f}.jsonl"
  [ -s "$p" ] || continue
  printf '%-18s ' "$f"
  /opt/enigma/.venv-agent/bin/python scripts/check_fallback_absent.py \
    --seed 42 --log "$p" 2>/dev/null \
    | grep -E '^iterations|^VERDICT' | tr '\n' ' '
  echo
done
