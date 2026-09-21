"""Feature -> qubit mapping strategies.

The mapping is an EXPERIMENTAL FACTOR, not preprocessing. Report results per
(dataset x feature-map x mapping x n_qubits) cell; collapsing over mapping
hides the most likely source of any effect.

All mappings fit on TRAIN ONLY and are reused on test. Fitting on the full
dataset leaks, and because quantum feature maps encode values directly into
rotation angles, the leak changes the circuits themselves rather than just
shifting a decision boundary.
"""

from __future__ import annotations

import numpy as np
from sklearn.decomposition import PCA
from functools import partial

from sklearn.feature_selection import SelectKBest, mutual_info_classif
from sklearn.preprocessing import MinMaxScaler

__all__ = ["MAPPINGS", "fit_mapping", "scale_to_angles"]

MAPPINGS = ("pca", "rff", "selectk")


def fit_mapping(X_train, y_train, n_qubits: int, strategy: str = "pca", seed: int = 0):
    """Fit a dimensionality reduction to n_qubits dims on the training fold.

    Returns (X_train_mapped, transform_fn). Apply transform_fn to the test fold.
    """
    X_train = np.asarray(X_train, dtype=float)
    if n_qubits > X_train.shape[1] and strategy != "rff":
        raise ValueError(
            f"n_qubits={n_qubits} exceeds feature count {X_train.shape[1]} for strategy "
            f"{strategy!r}; use 'rff' or reduce n_qubits."
        )

    if strategy == "pca":
        model = PCA(n_components=n_qubits, random_state=seed).fit(X_train)
        return model.transform(X_train), model.transform

    if strategy == "rff":
        rng = np.random.default_rng(seed)
        omega = rng.normal(scale=1.0, size=(X_train.shape[1], n_qubits))
        return X_train @ omega, lambda X: np.asarray(X, dtype=float) @ omega

    if strategy == "selectk":
        if y_train is None:
            raise ValueError("selectk mapping needs y_train")
        # mutual_info_classif adds random noise to break ties among continuous
        # features. Without random_state it is NON-DETERMINISTIC: two identical
        # runs on churn at k=4 selected different features and scored PR-AUC
        # 0.5199 vs 0.5664. Seeded so splits are reproducible bit-for-bit.
        score_fn = partial(mutual_info_classif, random_state=seed)
        model = SelectKBest(score_fn, k=n_qubits).fit(X_train, y_train)
        return model.transform(X_train), model.transform

    raise ValueError(f"Unknown mapping {strategy!r}; expected one of {MAPPINGS}")


def scale_to_angles(X_train, transform_fn=None, feature_range=(0.0, np.pi)):
    """Scale mapped features into a rotation-angle range, fit on train only.

    Quantum feature maps encode values as rotation angles. Values far outside
    [0, pi) wrap around the Bloch sphere and make distant points look similar,
    which produces a kernel that is valid-looking and meaningless. This is the
    most common silent failure in quantum kernel pipelines.

    Returns (X_train_angles, angle_transform_fn).
    """
    scaler = MinMaxScaler(feature_range=feature_range).fit(X_train)

    def _transform(X):
        X = np.asarray(X, dtype=float)
        if transform_fn is not None:
            X = transform_fn(X)
        return np.clip(scaler.transform(X), *feature_range)

    return scaler.transform(X_train), _transform
