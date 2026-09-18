#!/usr/bin/env bash
VENV=/opt/enigma/.venv-gpu
export TF_CPP_MIN_LOG_LEVEL=1

$VENV/bin/python - <<'PY'
import tensorflow as tf
import keras

print("tensorflow", tf.__version__)
print("keras", keras.__version__)
print("built with cuda:", tf.test.is_built_with_cuda())

gpus = tf.config.list_physical_devices("GPU")
print("physical GPUs:", gpus)

for gpu in gpus:
    details = tf.config.experimental.get_device_details(gpu)
    cc = details.get("compute_capability")
    print("  device_name:", details.get("device_name"))
    print("  compute_capability:", ".".join(str(v) for v in cc) if cc else None)

if not gpus:
    raise SystemExit("NO GPU VISIBLE TO TENSORFLOW")

import numpy as np
with tf.device("/GPU:0"):
    a = tf.random.normal((2048, 2048))
    b = tf.random.normal((2048, 2048))
    c = tf.matmul(a, b)
    print("matmul on GPU ok, result mean:", float(tf.reduce_mean(c)))

print("logical devices:", tf.config.list_logical_devices())
PY
