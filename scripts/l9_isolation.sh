#!/usr/bin/env bash
set -euo pipefail
cd "/mnt/f/XAI Project"
export CUDA_VISIBLE_DEVICES=-1
/opt/enigma/.venv-agent/bin/python scripts/level9_convergence_isolation.py \
  --seed 42 --threshold 0.30 --concurrency "${1:-40}" \
  > /tmp/l9_iso.out 2>/tmp/l9_iso.err
echo "EXIT $?"
tail -16 /tmp/l9_iso.out
