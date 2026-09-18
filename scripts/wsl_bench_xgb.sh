#!/usr/bin/env bash
set -e
VENV=/opt/enigma/.venv-gpu

$VENV/bin/python - <<'PY'
import json
import time
from pathlib import Path

import numpy as np
import xgboost as xgb

rng = np.random.default_rng(42)
rows, features, classes = 132000, 20, 11
x = rng.standard_normal((rows, features)).astype("float32")
y = rng.integers(0, classes, rows)

results = {}
for device in ["cuda", "cpu"]:
    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=6,
        tree_method="hist",
        device=device,
        objective="multi:softprob",
        num_class=classes,
        verbosity=0,
        n_jobs=-1,
    )
    model.fit(x[:64], y[:64])

    start = time.perf_counter()
    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=6,
        tree_method="hist",
        device=device,
        objective="multi:softprob",
        num_class=classes,
        verbosity=0,
        n_jobs=-1,
    )
    model.fit(x, y)
    elapsed = time.perf_counter() - start
    results[device] = round(elapsed, 3)
    print(f"xgboost device={device:<5} fit seconds: {elapsed:.3f}")

speedup = results["cpu"] / results["cuda"]
print(f"gpu speedup over cpu: {speedup:.2f}x")

out = Path("/mnt/f/XAI Project/results/bench/xgboost_device.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({
    "seed": 42,
    "rows": rows,
    "features": features,
    "classes": classes,
    "n_estimators": 200,
    "max_depth": 6,
    "fit_seconds": results,
    "gpu_speedup": round(speedup, 3),
}, indent=2), encoding="utf-8")
print(f"wrote {out}")
PY
