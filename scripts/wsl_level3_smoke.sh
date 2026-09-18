#!/usr/bin/env bash
ML_VENV=/opt/enigma/.venv-gpu
PROJ="/mnt/f/XAI Project"

export CUDA_VISIBLE_DEVICES=-1
export TF_CPP_MIN_LOG_LEVEL=2
export PYTHONUNBUFFERED=1

cd "$PROJ/Enigma-ML-Layer"
"$ML_VENV/bin/python" smoke_test_level3.py --seed 42 --records 100 "$@"
