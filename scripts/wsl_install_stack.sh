#!/usr/bin/env bash
set -e
VENV=/opt/enigma/.venv-gpu
PIP="$VENV/bin/python -m pip"

echo "=== versions before ==="
$VENV/bin/python -m pip list 2>/dev/null | grep -i -E "^numpy|^pandas|^scipy" || echo "none yet"

echo "=== installing pinned analysis stack ==="
$PIP install \
  --retries 10 \
  --timeout 120 \
  "scikit-learn==1.7.2" \
  "imbalanced-learn==0.14.0" \
  "keras-tuner==1.4.7" \
  "shap==0.48.0" \
  "xgboost==3.0.5" \
  "pandas==2.3.3" \
  "numpy==2.1.3" \
  "scipy==1.15.3" \
  "joblib==1.5.2" \
  "matplotlib==3.10.7" \
  "seaborn==0.13.2" \
  "websockets==15.0.1"

echo "=== pip check ==="
$PIP check || echo "pip check reported conflicts above"

echo "=== versions after ==="
$VENV/bin/python - <<'PY'
import importlib
for name in ["tensorflow","keras","sklearn","imblearn","keras_tuner","shap","xgboost","pandas","numpy","scipy","joblib","matplotlib","seaborn"]:
    try:
        module = importlib.import_module(name)
        print(f"{name:<18} {getattr(module, '__version__', 'unknown')}")
    except Exception as exc:
        print(f"{name:<18} IMPORT FAILED {type(exc).__name__}: {exc}")
PY

echo "=== tensorflow still sees gpu ==="
TF_CPP_MIN_LOG_LEVEL=2 $VENV/bin/python -c "import tensorflow as tf; print('GPUs:', tf.config.list_physical_devices('GPU'))"

echo "=== xgboost gpu check ==="
$VENV/bin/python - <<'PY'
import numpy as np
import xgboost as xgb

rng = np.random.default_rng(42)
x = rng.standard_normal((5000, 20)).astype("float32")
y = rng.integers(0, 11, 5000)

model = xgb.XGBClassifier(
    n_estimators=20,
    max_depth=4,
    tree_method="hist",
    device="cuda",
    objective="multi:softprob",
    num_class=11,
    verbosity=0,
)
model.fit(x, y)
booster = model.get_booster()
print("xgboost version:", xgb.__version__)
print("xgboost device config:", booster.attributes().get("device", "n/a"))
print("xgboost cuda fit ok, prediction shape:", model.predict_proba(x[:5]).shape)
PY
