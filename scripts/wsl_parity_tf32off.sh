#!/usr/bin/env bash
set -e
VENV=/opt/enigma/.venv-gpu
PROJ="/mnt/f/XAI Project"

export TF_CPP_MIN_LOG_LEVEL=2
export PYTHONUNBUFFERED=1
export NVIDIA_TF32_OVERRIDE=0
export TF_DETERMINISTIC_OPS=1
export TF_CUDNN_DETERMINISTIC=1

mkdir -p /opt/enigma/artifacts

$VENV/bin/python "$PROJ/Enigma-ML-Layer/train.py" \
  --data-dir /opt/enigma/data \
  --results-dir "$PROJ/results" \
  --artifacts-dir /opt/enigma/artifacts \
  --tuner-dir /opt/enigma/artifacts/tuner \
  --skip-tuning \
  --baseline-epochs 1 \
  --seed 42 \
  --run-name parity_wsl_gpu_tf32off
