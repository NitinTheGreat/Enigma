#!/usr/bin/env bash
set -e
VENV=/opt/enigma/.venv-gpu
PROJ="/mnt/f/XAI Project"
BENCH="$PROJ/Enigma-ML-Layer/bench_device.py"
OUT="$PROJ/results/bench"

export TF_CPP_MIN_LOG_LEVEL=2

echo "=== xgboost build info ==="
$VENV/bin/python - <<'PY'
import xgboost as xgb, json
info = xgb.build_info()
print("USE_CUDA:", info.get("USE_CUDA"))
print("USE_NCCL:", info.get("USE_NCCL"))
print("version:", info.get("libxgboost_version", xgb.__version__))
PY

echo
echo "=== GPU run ==="
$VENV/bin/python "$BENCH" --device gpu --epochs 10 --seed 42 --output "$OUT/wsl_gpu_seed42.json"

echo
echo "=== CPU run, same WSL environment ==="
$VENV/bin/python "$BENCH" --device cpu --epochs 10 --seed 42 --output "$OUT/wsl_cpu_seed42.json"
