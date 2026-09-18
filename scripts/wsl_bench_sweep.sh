#!/usr/bin/env bash
set -e
VENV=/opt/enigma/.venv-gpu
PROJ="/mnt/f/XAI Project"
BENCH="$PROJ/Enigma-ML-Layer/bench_device.py"
OUT="$PROJ/results/bench"

export TF_CPP_MIN_LOG_LEVEL=3

for BS in 32 128 512 2048; do
  for DEV in gpu cpu; do
    RESULT=$($VENV/bin/python "$BENCH" --device $DEV --epochs 3 --batch-size $BS --seed 42 \
      --output "$OUT/sweep_${DEV}_bs${BS}.json" 2>/dev/null | grep "mean steady epoch")
    echo "batch=${BS} device=${DEV} ${RESULT}"
  done
done
