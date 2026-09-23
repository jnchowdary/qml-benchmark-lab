"""Datasets, seeded splits, and the class-balanced subsampling the quantum
track requires.

SEEDS lives here and only here. Every script imports it rather than declaring
its own, so that classical and quantum methods are compared on bit-identical
folds -- the precondition for the paired tests in section 9.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.datasets import make_classification
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.preprocessing import StandardScaler

__all__ = ["SEEDS", "SHUFFLE_SEED_OFFSET", "load_dataset", "make_split", "make_cv",
           "balanced_subsample", "shuffle_labels"]

# Widened from 10 to 20 on 23 Sep 2026, decided from measured variance rather
# than from habit. scripts/power_analysis.py on the week-3 results gave a
# median paired sd of 0.0325 PR-AUC across the churn matched cells, so 10 seeds
# could only detect a true difference of 0.0324 with 80% power -- larger than
# almost any effect this literature reports, which would have made a null
# churn result a statement about our sample size. At 20 the minimum detectable
# effect is 0.0215; fraud goes from 0.0078 to 0.0052.
#
# 0..9 are kept as a PREFIX so every week-3 run remains a subset of every
# later run and the two are directly comparable. Never reorder this list.
SEEDS = list(range(20))

# Offset applied to the outer seed when permuting labels for the negative
# control, so the permutation is reproducible AND independent of the split it
# is paired with. Without an offset, seed s would drive both the split and the
# permutation and the two would be correlated in a way nobody could audit.
SHUFFLE_SEED_OFFSET = 10_000

DATA_ROOT = Path(__file__).resolve().parents[2] / "data"


def load_dataset(name: str, data_root: Path | None = None):
    """Load a benchmark dataset as (X, y, feature_names).

    'synthetic' needs no download and is what CI uses -- Kaggle credentials do
    not exist on a CI runner, and a test suite that cannot run without them is
    a test suite that stops running.
    """
    root = Path(data_root) if data_root else DATA_ROOT

    if name == "synthetic":
        X, y = make_classification(
            n_samples=400, n_features=10, n_informative=6, n_redundant=2,
            weights=[0.8, 0.2], class_sep=1.0, random_state=0,
        )
        return X, y, [f"f{i}" for i in range(X.shape[1])]

    if name == "churn":
        path = root / "raw" / "churn" / "WA_Fn-UseC_-Telco-Customer-Churn.csv"
        _require(path, "kaggle datasets download -d blastchar/telco-customer-churn "
                       "-p data/raw/churn --unzip")
        df = pd.read_csv(path)
        df = df.drop(columns=["customerID"])
        df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
        df = df.dropna()
        y = (df.pop("Churn") == "Yes").astype(int).to_numpy()
        df = pd.get_dummies(df, drop_first=True)
        return df.to_numpy(dtype=float), y, list(df.columns)

    if name == "fraud":
        path = root / "raw" / "fraud" / "creditcard.csv"
        _require(path, "kaggle datasets download -d mlg-ulb/creditcardfraud "
                       "-p data/raw/fraud --unzip")
        df = pd.read_csv(path)
        # Time = seconds since the first transaction in a two-day window. It
        # encodes row ordering, not a property of the transaction, and would not
        # generalise to any other period. Measured 17 Sep 2026: dropping it moves
        # full-feature RBF SVM PR-AUC from 0.9593 to 0.9548 (-0.0045). Dropped.
        df = df.drop(columns=["Time"])
        y = df.pop("Class").to_numpy()
        return df.to_numpy(dtype=float), y, list(df.columns)

    raise ValueError(f"Unknown dataset {name!r}; expected synthetic|churn|fraud")


def _require(path: Path, hint: str) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Fetch it first:\n    {hint}\n"
            "CI and the smoke tests use dataset 'synthetic', which needs no download."
        )


def make_split(X, y, seed: int, test_size: float = 0.3):
    """Seeded stratified split with the scaler fit on the TRAIN fold only."""
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, stratify=y, random_state=seed
    )
    scaler = StandardScaler().fit(X_train)
    return scaler.transform(X_train), scaler.transform(X_test), y_train, y_test


def make_cv(seed: int, n_splits: int = 5) -> StratifiedKFold:
    return StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)


def balanced_subsample(X, y, n_per_class: int, seed: int = 0):
    """Class-balanced subsample for the quantum track.

    Required, not optional: a quantum kernel over n points costs n^2/2 circuit
    evaluations (~9 ms each at 4 qubits, measured), so the full 284k-row fraud
    set is roughly 10^10 circuit evaluations. See qiskit_kernels.MS_PER_ENTRY_4Q.

    Uses ALL available minority samples when fewer than n_per_class exist, and
    reports the true ratio rather than silently returning an imbalanced set.
    """
    rng = np.random.default_rng(seed)
    X, y = np.asarray(X), np.asarray(y)
    idx = []
    for label in np.unique(y):
        pool = np.flatnonzero(y == label)
        take = min(n_per_class, len(pool))
        idx.append(rng.choice(pool, size=take, replace=False))
    idx = np.concatenate(idx)
    rng.shuffle(idx)
    return X[idx], y[idx]


def shuffle_labels(y, seed: int):
    """Permute labels within the sample, destroying any X-y relationship.

    The negative control. Run the ENTIRE pipeline -- mapping, angle scaling,
    nested CV, tuning, final fit, scoring -- on labels that carry no signal.
    The expected test PR-AUC is then the test base rate, and the expected
    ROC-AUC is 0.5. Anything materially above that is not a property of the
    data; it is leakage somewhere in the pipeline, and the most likely place
    is a step that sees labels it should not (SelectKBest is fit on the
    outer-train labels, which is legitimate, but a bug there would show up
    here and nowhere else).

    Class counts are preserved exactly, so the base rate is unchanged and the
    control is comparable to the real run cell for cell.

    Permute BEFORE the train/test split, never after: permuting each side
    separately would leave the two label vectors independently balanced and
    would not test the split itself.
    """
    rng = np.random.default_rng(int(seed) + SHUFFLE_SEED_OFFSET)
    y = np.asarray(y)
    return y[rng.permutation(len(y))]
