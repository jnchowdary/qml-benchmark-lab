#!/usr/bin/env python3
"""The reference audit hook: this project's adapter, and the worked example.

WHY A HOOK AT ALL
-----------------
Four of the audit's checks cannot be answered from a results file, because the
file records what a model scored and they ask about the kernel that produced it.
Tier 2 listed them as NOT RUN and stopped there. That was honest but it was also
the wrong place to stop, because the two largest findings in this project were
both invisible from records:

  - the bandwidth asymmetry, which made the whole comparison measure tuning;
  - the surrogate degeneracy, which showed the tuned quantum kernels were
    Gaussian kernels reached expensively.

An audit that cannot see either of those can certify a file that is worthless.

So the audit does not try to import a foreign pipeline. The pipeline hands it a
small module instead, and this is that module for qbench. Anyone auditing their
own work writes the equivalent: three optional functions, no base class, no
registration, no import of `audit` itself.

    gram(record)           -> (n_train, n_train) training Gram matrix
    training_data(record)  -> (X_train, y_train)
    refit(record, K)       -> a record-shaped dict for an arbitrary kernel

A check that needs a function this module does not define reports NOT RUN and
names the missing function. It never guesses, and it never treats "the hook did
not provide this" as "the pipeline passed".

ONE WARNING, WHICH IS THE POINT OF WRITING IT DOWN
--------------------------------------------------
A hook that rebuilds the split DIFFERENTLY from the pipeline that wrote the
records will produce confident, wrong readings: the audit would be auditing a
kernel the experiment never used. The defence here is that every function below
reaches the split through the same `qbench.data` and `qbench.features` calls the
runner uses, in the same order, seeded from the record; and that `refit` checks
the resulting test-label fingerprint against the record's and raises when they
differ rather than returning a number. Copy that check into your own hook. It is
the one line that makes the rest of it trustworthy.

Usage:
    PYTHONPATH=src python scripts/audit.py RESULTS.jsonl \
        --hook scripts/audit_hook_qbench.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from sklearn.metrics.pairwise import rbf_kernel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from qbench.data import balanced_subsample, load_dataset, make_split  # noqa: E402
from qbench.features import fit_mapping, scale_to_angles  # noqa: E402
from qbench.kernels.quantum import QuantumGramFactory  # noqa: E402
from qbench.tuning import tune_and_evaluate  # noqa: E402

_SPLITS: dict = {}


def _split(record):
    """Rebuild the exact split a record was scored on. Cached: audits resample
    the same cells repeatedly and the mapping fit is the expensive part."""
    key = (record["dataset"], int(record["n_per_class"]), int(record["seed"]),
           record["mapping"], int(record["n_qubits"]))
    if key in _SPLITS:
        return _SPLITS[key]
    dataset, n_per_class, seed, mapping, nq = key
    X, y, _ = load_dataset(dataset)
    Xs, ys = balanced_subsample(X, y, n_per_class=n_per_class, seed=seed)
    X_tr, X_te, y_tr, y_te = make_split(Xs, ys, seed=seed)
    Xm, transform = fit_mapping(X_tr, y_tr, nq, mapping, seed=seed)
    Xa_tr, to_angles = scale_to_angles(Xm)
    out = (Xa_tr, y_tr, to_angles(transform(X_te)), y_te, nq, seed)
    _SPLITS[key] = out
    return out


def gram(record):
    """Training Gram matrix for this record's kernel.

    Only quantum records have one to rebuild; the audit samples records and
    tolerates a raise, so a classical record simply declines to answer rather
    than silently returning an RBF the check would then report on.
    """
    if "embedding" not in record:
        raise ValueError("not a quantum record: no embedding to rebuild")
    Xa_tr, _, _, _, nq, _ = _split(record)
    params = {"embedding": record["embedding"], "reps": int(record["reps"]),
              "bandwidth": float(record.get("bandwidth", 1.0))}
    return np.asarray(QuantumGramFactory(nq).gram_fn(params)(Xa_tr), dtype=float)


def training_data(record):
    """X_train, y_train, in the angle-scaled representation the kernels see."""
    Xa_tr, y_tr, _, _, _, _ = _split(record)
    return Xa_tr, y_tr


def refit(record, gamma):
    """Score an RBF surrogate through the identical pipeline on this split.

    The fingerprint check is not optional. Without it the surrogate could be
    scored on different test points than the record and the difference would
    still look like a result.
    """
    Xa_tr, y_tr, Xa_te, y_te, _, seed = _split(record)
    out = tune_and_evaluate(
        f"rbf-surrogate-g{gamma:.3e}",
        lambda p: (lambda A, B=None: rbf_kernel(A, A if B is None else B, gamma=gamma)),
        [{}], Xa_tr, y_tr, Xa_te, y_te, seed=seed)
    fp = record.get("test_label_fingerprint")
    if fp and out.get("test_label_fingerprint") != fp:
        raise RuntimeError(
            f"hook rebuilt a different split than record seed={record.get('seed')} "
            f"was scored on. Any comparison from here would be meaningless.")
    return out
