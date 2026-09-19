#!/usr/bin/env bash
set -euo pipefail
cd "/mnt/f/XAI Project"
export CUDA_VISIBLE_DEVICES=-1
/opt/enigma/.venv-agent/bin/python scripts/level9_cache_ablation.py \
  --seed "${2:-42}" --limit "${1:-4}" \
  --cache results/scenarios/gemini_cache_real.json \
  2>/tmp/l9_cache.err
echo "EXIT $?"
