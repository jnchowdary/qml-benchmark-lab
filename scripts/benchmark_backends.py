#!/usr/bin/env python3
"""Measure quantum kernel cost ON THE MACHINE THAT WILL RUN THE EXPERIMENTS.

Why this exists
---------------
The cost model this project has been planning against (9.0 ms/entry for Qiskit,
2.2 ms/entry for PennyLane default.qubit, both at 4 qubits) was measured on a
Linux container, not on the machine the experiments run on. Every week-4 and
week-5 schedule, every subsample size, and the decision to cap the matched
track at 250 points per class rest on those two numbers. If the real machine is
three times slower, the plan is wrong by a factor of three and nobody finds out
until a run that was supposed to take an evening takes two days.

`lightning.qubit` was never benchmarked at all. It is a compiled C++
statevector simulator, it is a drop-in replacement for `default.qubit`, and if
it is meaningfully faster it changes what is affordable -- possibly enough to
raise the subsample size, which is the single biggest lever on statistical
power (see scripts/power_analysis.py).

What it measures
----------------
Per-entry wall-clock for each available backend at each qubit count, on a small
square Gram matrix, then extrapolates to the real week-4 workload. Per-entry
cost is the right unit because a Gram matrix over n points is n(n-1)/2 entries
and that count is fixed by the design, not by the backend.

It also CHECKS AGREEMENT: every backend here is an exact statevector simulator,
so their Gram matrices must agree. A backend that is fast because it is
computing something else is not a speedup. Disagreement is reported as a
failure and the backend is excluded from the recommendation.

Usage:
    PYTHONPATH=src python scripts/benchmark_backends.py
    PYTHONPATH=src python scripts/benchmark_backends.py --qubits 4 6 8 --n 24
    PYTHONPATH=src python scripts/benchmark_backends.py --skip-qiskit   # faster
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# The week-4 workload this extrapolates to: matched track, 250 per class,
# 70/30 split -> 350 train, 150 test. One kernel matrix per structural setting
# per seed, train block plus test block.
N_TRAIN, N_TEST = 350, 150
TRAIN_ENTRIES = N_TRAIN * (N_TRAIN - 1) // 2
TEST_ENTRIES = N_TEST * N_TRAIN
WORKLOAD_ENTRIES = TRAIN_ENTRIES + TEST_ENTRIES

AGREEMENT_TOL = 1e-8


def sample(n, d, seed=0):
    """Angle-scaled features, the same range the real pipeline produces."""
    return np.random.default_rng(seed).uniform(0.0, np.pi, size=(n, d))


def time_gram(build, X, repeats=1):
    """(seconds per entry, Gram matrix). Timed on the square block only."""
    n = len(X)
    entries = n * (n - 1) / 2
    best = None
    K = None
    for _ in range(repeats):
        kernel = build()
        t0 = time.perf_counter()
        K = np.asarray(kernel.evaluate(X), dtype=float)
        dt = time.perf_counter() - t0
        best = dt if best is None else min(best, dt)
    return best / entries, K


def pennylane_backends(skip):
    if skip:
        return []
    try:
        from qbench.kernels.pennylane_kernels import available_devices
    except Exception as exc:  # noqa: BLE001
        print(f"  pennylane unavailable: {exc}")
        return []
    return available_devices()


def build_pennylane(device, nq):
    from qbench.kernels.pennylane_kernels import build_pennylane_kernel
    return lambda: build_pennylane_kernel(nq, embedding="angle", reps=1, device=device)


def build_qiskit(nq):
    from qbench.kernels.qiskit_kernels import build_qiskit_kernel
    return lambda: build_qiskit_kernel(nq, reps=2, entanglement="linear", feature_map="zz")


def fmt_hours(seconds):
    if seconds < 90:
        return f"{seconds:.0f}s"
    if seconds < 5400:
        return f"{seconds / 60:.1f}m"
    return f"{seconds / 3600:.1f}h"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qubits", type=int, nargs="+", default=[4, 6, 8])
    ap.add_argument("--n", type=int, default=24,
                    help="points in the timing Gram matrix (n(n-1)/2 entries)")
    ap.add_argument("--repeats", type=int, default=2, help="take the fastest of this many runs")
    ap.add_argument("--skip-qiskit", action="store_true")
    ap.add_argument("--skip-pennylane", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "results" / "analysis" / "backend_benchmark.json"))
    args = ap.parse_args()

    entries = args.n * (args.n - 1) // 2
    print(f"machine: {platform.platform()}")
    print(f"python : {platform.python_version()}  |  processor: {platform.processor() or 'unknown'}")
    print(f"timing : n={args.n} ({entries} entries per Gram), fastest of {args.repeats}\n")

    devices = pennylane_backends(args.skip_pennylane)
    print(f"pennylane devices usable here: {devices or 'none'}")
    print(f"qiskit: {'skipped' if args.skip_qiskit else 'included'}\n")

    rows = []
    for nq in args.qubits:
        X = sample(args.n, nq, seed=nq)
        reference = None
        print(f"--- {nq} qubits ---")
        backends = [(f"pennylane/{d}", build_pennylane(d, nq)) for d in devices]
        if not args.skip_qiskit:
            backends.append(("qiskit/statevector", build_qiskit(nq)))
        for label, build in backends:
            try:
                per_entry, K = time_gram(build, X, repeats=args.repeats)
            except Exception as exc:  # noqa: BLE001
                print(f"  {label:<26} FAILED: {type(exc).__name__}: {exc}")
                rows.append({"n_qubits": nq, "backend": label, "error": f"{type(exc).__name__}: {exc}"})
                continue
            ms = per_entry * 1000
            # Agreement is checked only within PennyLane: the Qiskit kernel uses
            # a ZZ feature map and PennyLane an angle embedding, so they encode
            # different circuits and SHOULD differ. Comparing them would be a
            # category error.
            agree = None
            if label.startswith("pennylane/"):
                if reference is None:
                    reference = K
                else:
                    agree = float(np.abs(K - reference).max())
            total = WORKLOAD_ENTRIES * per_entry
            flag = ""
            if agree is not None and agree > AGREEMENT_TOL:
                flag = f"  !! DISAGREES by {agree:.2e} - EXCLUDE"
            print(f"  {label:<26} {ms:8.3f} ms/entry   one kernel matrix {fmt_hours(total):>7}{flag}")
            rows.append({"n_qubits": nq, "backend": label, "ms_per_entry": ms,
                         "workload_seconds": total,
                         "max_abs_disagreement": agree})
        print()

    print(f"workload assumed: {N_TRAIN} train + {N_TEST} test = {WORKLOAD_ENTRIES:,} entries "
          f"per kernel matrix, per seed, per structural setting.\n")

    ok = [r for r in rows if "ms_per_entry" in r
          and not (r["max_abs_disagreement"] and r["max_abs_disagreement"] > AGREEMENT_TOL)]
    if ok:
        print("BUDGET at the measured rates (10 seeds x one structural setting):")
        for nq in args.qubits:
            at_q = [r for r in ok if r["n_qubits"] == nq]
            if not at_q:
                continue
            fastest = min(at_q, key=lambda r: r["ms_per_entry"])
            print(f"  {nq} qubits: fastest is {fastest['backend']} at {fastest['ms_per_entry']:.3f} ms/entry"
                  f"  ->  10 seeds = {fmt_hours(10 * fastest['workload_seconds'])}")
        print("\nMultiply by the number of structural settings in the quantum grid, and again")
        print("by the number of (mapping, qubit) cells, before promising anyone a date.")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "measured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "n_timing_points": args.n,
        "repeats": args.repeats,
        "workload": {"n_train": N_TRAIN, "n_test": N_TEST, "entries": WORKLOAD_ENTRIES},
        "results": rows,
    }
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"\n-> {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")


if __name__ == "__main__":
    main()
