import json
from pathlib import Path

import pandas as pd

DATA = Path("/mnt/f/XAI Project/data")
POOL_FILE = "UNSW_NB15_testing-set.csv"
TEST_FILE = "UNSW_NB15_training-set.csv"

pool = pd.read_csv(DATA / POOL_FILE, low_memory=False)
test = pd.read_csv(DATA / TEST_FILE, low_memory=False)

print(f"pool ({POOL_FILE}): {pool.shape}")
print(f"test ({TEST_FILE}): {test.shape}")
print()

print("=== exact attack_cat values in pool ===")
for name, count in pool["attack_cat"].value_counts().items():
    print(f"  {name!r:<20} {count}")
print()

print("=== exact attack_cat values in test ===")
for name, count in test["attack_cat"].value_counts().items():
    print(f"  {name!r:<20} {count}")
print()

pool_labels = set(pool["attack_cat"].unique())
test_labels = set(test["attack_cat"].unique())
print(f"labels only in pool: {pool_labels - test_labels}")
print(f"labels only in test: {test_labels - pool_labels}")
print(f"label count pool={len(pool_labels)} test={len(test_labels)}")
print()

normalised = {str(v).strip().lower() for v in pool_labels}
print(f"after strip+lower, distinct labels: {len(normalised)}")
print(f"  {sorted(normalised)}")
print()

print("=== dtypes ===")
by_kind = {}
for column, dtype in pool.dtypes.items():
    by_kind.setdefault(str(dtype), []).append(column)
for dtype, columns in sorted(by_kind.items()):
    print(f"  {dtype}: {len(columns)} -> {columns}")
print()

print("=== categorical cardinalities ===")
for column in pool.select_dtypes(include=["object"]).columns:
    pool_unique = pool[column].nunique()
    test_unique = test[column].nunique()
    unseen = set(test[column].unique()) - set(pool[column].unique())
    print(f"  {column:<12} pool={pool_unique:<5} test={test_unique:<5} unseen_in_test={len(unseen)}")
print()

print("=== nulls ===")
nulls = pool.isnull().sum()
print(f"  columns with nulls: {list(nulls[nulls > 0].index) or 'none'}")
print()

print("=== label column vs attack_cat ===")
print(pool.groupby("attack_cat")["label"].agg(["min", "max", "mean"]).to_string())
print()

print("=== id column ===")
print(f"  pool id range: {pool['id'].min()} to {pool['id'].max()}, unique={pool['id'].nunique()}")
print(f"  test id range: {test['id'].min()} to {test['id'].max()}, unique={test['id'].nunique()}")
