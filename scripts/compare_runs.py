#!/usr/bin/env python3
"""Compare two run directories record by record.

Written 25 Sep 2026 to prove that the statevector formulation of the quantum
kernel reproduces the pairwise fidelity protocol ON REAL DATA, not only on
synthetic arrays in a unit test. The tests assert agreement to 1e-12 at 4 and
8 qubits on random points; this checks the actual control runs, at the actual
qubit count, through the whole pipeline including tuning and scoring.

The same tool answers the general question "did this change alter any result",
which is worth having for every future optimisation.

Usage:
    PYTHONPATH=src python scripts/compare_runs.py results/runs/quantum /tmp/qverify
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

KEY = ("seed", "mapping", "n_qubits", "setting", "method")
METRICS = ("test_average_precision", "test_roc_auc", "test_f1", "inner_score")


def load(path):
    out = {}
    for line in path.open():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        out[tuple(r.get(k) for k in KEY)] = r
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--tol", type=float, default=1e-9)
    args = ap.parse_args()
    A, B = Path(args.a), Path(args.b)

    names = sorted({p.name for p in A.glob("*.jsonl")} & {p.name for p in B.glob("*.jsonl")})
    if not names:
        raise SystemExit(f"no common .jsonl files between {A} and {B}")

    failed = False
    for name in names:
        a, b = load(A / name), load(B / name)
        only_a, only_b = set(a) - set(b), set(b) - set(a)
        worst_metric, worst_key, worst_val = None, None, 0.0
        for k in set(a) & set(b):
            for m in METRICS:
                if m in a[k] and m in b[k] and a[k][m] is not None and b[k][m] is not None:
                    d = abs(a[k][m] - b[k][m])
                    if d > worst_val:
                        worst_metric, worst_key, worst_val = m, k, d
        # per-test-point scores, the thing week 9's tests actually use
        worst_score = 0.0
        for k in set(a) & set(b):
            sa, sb = a[k].get("test_decision_scores"), b[k].get("test_decision_scores")
            if sa and sb and len(sa) == len(sb):
                worst_score = max(worst_score, max(abs(x - y) for x, y in zip(sa, sb)))

        ok = not only_a and not only_b and worst_val <= args.tol and worst_score <= args.tol
        failed |= not ok
        print(f"{'OK  ' if ok else 'FAIL'} {name}: {len(set(a) & set(b))} common records")
        if only_a or only_b:
            print(f"       only in {A.name}: {len(only_a)}   only in {B.name}: {len(only_b)}")
        print(f"       largest metric difference        {worst_val:.2e}"
              + (f"  ({worst_metric}, {worst_key})" if worst_metric else ""))
        print(f"       largest decision-score difference {worst_score:.2e}")

    print("\n" + ("DIFFERENCES FOUND" if failed else
                  f"identical to within {args.tol:g}: the change altered no result"))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
