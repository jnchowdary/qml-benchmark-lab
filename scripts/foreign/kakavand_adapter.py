#!/usr/bin/env python3
"""Read the Kakavand et al. hardware deposit as audit records, and as a hook.

WHY THIS FILE EXISTS
--------------------
The audit protocol's README claims it "runs against any pipeline that can emit
a documented record format". Until now it has only ever been run against the
pipeline that wrote it, and every check in it was written after a failure in
that same pipeline. This is the first foreign test.

The subject is the reproducibility deposit for Kakavand, Strohmeyer & Schlotter
(2026), arXiv:2604.18837, Zenodo 10.5281/zenodo.19197916, CC BY 4.0. It contains
per-experiment records for the six IBM hardware runs HW-01 to HW-06 -- the
measured 60x60 Gram matrices, which they kept precisely because they cannot be
regenerated without buying QPU time again. The 970 simulation experiments are
regenerable and were not deposited.

WHAT THIS ADAPTER DOES NOT DO, WHICH IS THE POINT
-------------------------------------------------
It does not invent fields. Their endpoint is balanced accuracy; the audit's
schema requires average precision and ROC-AUC. Those are different quantities
and mapping one onto the other's field name would be falsifying a foreign
group's results to make our own tool look applicable. So they are left absent,
`check_schema` reports them missing, and every check that needs them reports
what it cannot answer. That report is the result of this exercise.

WHAT THEIR SCHEMA DOES CARRY, AND ONE PLEASANT SURPRISE
-------------------------------------------------------
  method            three arms per experiment: hardware, ideal, noisy. All
                    three are quantum -- there is no classical arm in the
                    hardware phase, so cross-arm has nothing to compare.
  seed              config.seed = 42, the same for every experiment. One split.
  n_train           n_sub = 60, scored by 5-fold CV rather than a held-out set.
  configuration     dataset, reducer, feature_map, k_features, n_qubits, shots
  split fingerprint they record `subsample_indices`: which 60 of the source
                    dataset's rows were used. That is not a label fingerprint,
                    but it identifies the split exactly, and it means pairing
                    CAN be verified here -- which this protocol's own records
                    only manage because a fingerprint field was added in week 3.
                    A foreign schema solved the same problem a different way.

Usage:
    python scripts/foreign/kakavand_adapter.py \
        --deposit ~/Documents/foreign-audit/extracted/QSVM-Benchmark-Paper \
        --out results/audits/kakavand_hw.jsonl

    KAKAVAND_DEPOSIT=~/Documents/foreign-audit/extracted/QSVM-Benchmark-Paper \
    PYTHONPATH=src python scripts/audit.py results/audits/kakavand_hw.jsonl \
        --hook scripts/foreign/kakavand_adapter.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np

ARMS = {"hw": "hardware", "ideal": "ideal-sim", "noisy": "noisy-sim"}


def deposit_root(explicit=None):
    p = explicit or os.environ.get("KAKAVAND_DEPOSIT")
    if not p:
        raise SystemExit("set KAKAVAND_DEPOSIT or pass --deposit: the path to "
                         "the extracted QSVM-Benchmark-Paper directory")
    return Path(p).expanduser()


def _square_array(npz):
    """Their npz key names are not documented, so find the Gram by shape rather
    than by guessing a name: the one square 2-D float array in the file."""
    cands = [k for k in npz.files
             if npz[k].ndim == 2 and npz[k].shape[0] == npz[k].shape[1]]
    if len(cands) != 1:
        raise KeyError(f"expected exactly one square 2-D array, found "
                       f"{cands or list(npz.files)}")
    return np.asarray(npz[cands[0]], dtype=float)


def load_deposit(root):
    """One record per (experiment, arm). Fields they do not have stay absent."""
    hw_dir = Path(root) / "results" / "phase3_hardware"
    out = []
    for d in sorted(p for p in hw_dir.iterdir() if p.is_dir()):
        rj = d / "result.json"
        if not rj.exists():
            continue
        r = json.loads(rj.read_text())
        idx = r.get("subsample_indices") or []
        # Their equivalent of a split fingerprint, order-sensitive like ours.
        fp = hashlib.sha256(",".join(map(str, idx)).encode()).hexdigest()[:16]
        meta = r.get("hardware_metadata", {})
        cfg = r.get("config", {})
        for arm, res in (r.get("svm_results") or {}).items():
            out.append({
                "method": ARMS.get(arm, arm),
                "seed": int(cfg.get("seed", -1)),
                "n_train": int(r.get("n_sub", 0)),
                "experiment_id": r.get("experiment_id"),
                "dataset": r.get("dataset"),
                "reducer": r.get("reducer"),
                "feature_map": r.get("feature_map"),
                "k_features": r.get("k_features"),
                "n_qubits": meta.get("n_qubits"),
                "shots": r.get("shots"),
                "split_fingerprint": fp,
                # Their endpoint. Deliberately NOT renamed to an audit field:
                # balanced accuracy is not average precision and is not ROC-AUC.
                "test_balanced_accuracy": res.get("balanced_accuracy"),
                "balanced_accuracy_std": res.get("ba_std"),
                "selected_C": res.get("best_C"),
                "final_converged": True,
            })
    if not out:
        raise SystemExit(f"no result.json found under {hw_dir}")
    return out


# ------------------------------------------------------------------ the hook

def gram(record):
    """Training Gram matrix for this record.

    Only the `hardware` arm has a deposited matrix; the ideal and noisy arms
    were simulated and their kernels are among the 3.3 GB that was, reasonably,
    not deposited. Raising here rather than substituting the hardware matrix is
    the difference between auditing their kernel and auditing a stand-in.
    """
    if record.get("method") != "hardware":
        raise ValueError(f"no deposited kernel for the {record.get('method')} "
                         f"arm; only the hardware matrices were kept")
    p = (deposit_root() / "results" / "phase3_hardware" /
         str(record["experiment_id"]) / "K_hardware.npz")
    if not p.exists():
        raise FileNotFoundError(p)
    with np.load(p) as z:
        return _square_array(z)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--deposit")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    root = deposit_root(args.deposit)
    recs = load_deposit(root)
    p = Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in recs))

    fields = sorted({k for r in recs for k in r})
    required = ["method", "seed", "n_train", "n_test", "test_base_rate",
                "test_average_precision", "test_roc_auc"]
    missing = [f for f in required if f not in fields]
    print(f"{len(recs)} records from {len({r['experiment_id'] for r in recs})} "
          f"experiments x {len({r['method'] for r in recs})} arms")
    print(f"  seeds present: {sorted({r['seed'] for r in recs})}")
    print(f"  fields: {', '.join(fields)}")
    print(f"  REQUIRED FIELDS ABSENT: {', '.join(missing) or 'none'}")
    print(f"  Their endpoint is balanced accuracy. It is not renamed to an "
          f"audit field,\n  so the checks that need average precision or "
          f"ROC-AUC will say they cannot answer.")
    print(f"-> {p}")


if __name__ == "__main__":
    main()
