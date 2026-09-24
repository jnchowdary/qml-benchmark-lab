#!/usr/bin/env python3
"""Is the hyperparameter grid too narrow, or is its edge a plateau?

THE QUESTION
------------
In the 23 Sep 2026 runs, between 265 and 350 of the 900 tuned models in each
matched file chose a hyperparameter at the edge of its searched range, and the
plateau-aware rule removed none of them. Both edges are involved, and the
pattern differs by dataset. On churn at 250 per class: polynomial gamma at the
minimum 133 times and at the maximum 46, degree at the minimum 88 and at the
maximum 72, RBF gamma at the minimum 94. On fraud the largest single flag is
polynomial degree at its MAXIMUM, 106 of 300, where the grid stops at 5.

Two explanations fit and they demand opposite actions.

  UNDER-TUNED  The optimum lies outside the grid. The classical baseline is
               then not tuned, and under-tuning the classical side is the most
               common way this literature manufactures an apparent quantum
               advantage. Action: widen the grid and re-run week 3.

  PLATEAU      The score is flat near the edge, so the tie-break picks the
               boundary value. Action: leave the grid alone and loosen the
               plateau tolerance in edge_flags, which is 1e-12 and therefore
               cannot see a region flat to four decimals but not to twelve.

WHAT THIS MEASURES
------------------
For each cell it runs the inner-CV selection twice: once on the frozen grid,
once on the frozen grid extended in BOTH directions. It reports how often the
winner leaves the frozen grid, in which direction, and how much the inner
score improves.

Testing only the lower edge, as the first version of this script did, would
answer half the question and declare the grid clean on the strength of it.

INNER-CV SCORES ONLY. No outer test score is read, computed or reported.
Widening a grid on the strength of a test score would be selection on the test
set, which is the failure this project exists to avoid committing.

HOW TO READ THE RESULT
----------------------
Compare the MAXIMUM gain against the minimum detectable effect for the same
cell from scripts/power_analysis.py, not against a threshold someone chose.
If the best possible gain from a wider grid is a small fraction of the
smallest difference the experiment can resolve, the grid cannot be costing
anything measurable, whatever the flag counts say. The printed verdict does
this comparison when --mde is supplied.

Usage:
    PYTHONPATH=src python scripts/check_grid_edges.py --dataset churn --mde 0.0159
    PYTHONPATH=src python scripts/check_grid_edges.py --dataset fraud --mde 0.0056
    PYTHONPATH=src python scripts/check_grid_edges.py --dataset churn --direction down
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import sys
import time
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qbench.data import SEEDS, balanced_subsample, load_dataset, make_split, shuffle_labels  # noqa: E402
from qbench.features import MAPPINGS, fit_mapping, scale_to_angles  # noqa: E402
from qbench.kernels.classical import build_classical_kernel  # noqa: E402
from qbench.tuning import (  # noqa: E402
    C_GRID,
    POLY_DEGREES,
    POLY_MULTIPLIERS,
    matched_grids,
    select_hyperparameters,
)

# Frozen grid, for reference: RBF gamma 1e-3 .. 1e2 in half-decades; poly
# degree 2..5, multiplier 0.1/1/3/10, coef0 0/1.
EXTRA_RBF_LOW = tuple(float(g) for g in np.round(10.0 ** np.arange(-5.0, -1.01, 0.5), 12))
EXTRA_RBF_HIGH = tuple(float(g) for g in np.round(10.0 ** np.arange(2.5, 4.01, 0.5), 12))
EXTRA_POLY_MULT_LOW = (0.003, 0.01, 0.03)
EXTRA_POLY_MULT_HIGH = (30.0, 100.0)
# Extended to 9 on 23 Sep 2026. The first two-sided run capped the extension at
# degree 7, and degree 7 turned out to be the single best setting on BOTH
# datasets (+0.00712 churn, +0.00586 fraud, both at multiplier 10, coef0 1).
# Freezing the grid at 7 would therefore have moved the edge rather than removed
# it. The extension now runs until the solver stops converging, which is a
# boundary set by numerics and can be stated as such, rather than by whatever
# number happened to be typed here.
EXTRA_POLY_DEGREES = (6, 7, 8, 9)


def _key(p):
    return tuple(sorted((k, round(float(v), 12)) for k, v in p.items()))


def extended_grids(d, direction="both"):
    """The frozen grid plus an extension, built by ADDING to matched_grids(d).

    Constructed as a superset by construction, never re-derived, so the
    comparison is between a grid and its extension rather than between two
    different grids. A test asserts the containment.
    """
    base = matched_grids(d)
    rbf_extra, poly_mult_extra, poly_deg_extra = [], [], []
    if direction in ("down", "both"):
        rbf_extra += list(EXTRA_RBF_LOW)
        poly_mult_extra += list(EXTRA_POLY_MULT_LOW)
    if direction in ("up", "both"):
        rbf_extra += list(EXTRA_RBF_HIGH)
        poly_mult_extra += list(EXTRA_POLY_MULT_HIGH)
        poly_deg_extra += list(EXTRA_POLY_DEGREES)

    seen_rbf = {_key(p) for p in base["rbf"]}
    rbf = base["rbf"] + [p for p in ({"gamma": g} for g in rbf_extra) if _key(p) not in seen_rbf]

    all_mult = list(POLY_MULTIPLIERS) + poly_mult_extra
    all_deg = list(POLY_DEGREES) + poly_deg_extra
    seen_poly = {_key(p) for p in base["poly"]}
    poly = base["poly"] + [
        p for p in (
            {"degree": deg, "gamma": float(m / (d * np.pi**2)), "coef0": c0}
            for deg in all_deg for m in all_mult for c0 in (0.0, 1.0)
        ) if _key(p) not in seen_poly
    ]
    return {"rbf": rbf, "poly": poly}


def classify(params, base_grid):
    """'inside', or which way the chosen point left the frozen grid.

    Membership is decided by set difference against the frozen grid, not by
    comparing one parameter: a degree-6 point is outside the grid even though
    its gamma is inside, and the first version of this script would have
    called it inside.
    """
    if _key(params) in {_key(p) for p in base_grid}:
        return "inside"
    lo_g = min(p["gamma"] for p in base_grid)
    hi_g = max(p["gamma"] for p in base_grid)
    if "degree" in params and params["degree"] > max(p["degree"] for p in base_grid):
        return "degree-up"
    if params["gamma"] < lo_g * (1 - 1e-9):
        return "gamma-down"
    if params["gamma"] > hi_g * (1 + 1e-9):
        return "gamma-up"
    return "other"


def at_frozen_edge(params, base_grid):
    """Did the frozen-grid winner sit on a boundary, and which one."""
    out = []
    gammas = sorted({p["gamma"] for p in base_grid})
    if params["gamma"] <= gammas[0] * (1 + 1e-9):
        out.append("gamma-min")
    if params["gamma"] >= gammas[-1] * (1 - 1e-9):
        out.append("gamma-max")
    if "degree" in params:
        degs = sorted({p["degree"] for p in base_grid})
        if params["degree"] == degs[0]:
            out.append("degree-min")
        if params["degree"] == degs[-1]:
            out.append("degree-max")
    return out


def gram_fn(name):
    return lambda p: build_classical_kernel(name, **p)


def run_cell(X, y, seed, n_per_class, mapping, nq, direction, shuffle=False):
    Xs, ys = balanced_subsample(X, y, n_per_class=n_per_class, seed=seed)
    if shuffle:
        ys = shuffle_labels(ys, seed)
    X_tr, _, y_tr, _ = make_split(Xs, ys, seed=seed)   # test split discarded, deliberately
    if mapping != "randproj" and nq > X_tr.shape[1]:
        return []
    Xm, _ = fit_mapping(X_tr, y_tr, nq, mapping, seed=seed)
    Xa_tr, _ = scale_to_angles(Xm)
    d = Xa_tr.shape[1]
    base, ext = matched_grids(d), extended_grids(d, direction)

    out = []
    for kernel in ("rbf", "poly"):
        a = select_hyperparameters(gram_fn(kernel), base[kernel], Xa_tr, y_tr, seed=seed)
        b = select_hyperparameters(gram_fn(kernel), ext[kernel], Xa_tr, y_tr, seed=seed)
        out.append({
            "seed": seed, "mapping": mapping, "n_qubits": nq, "kernel": kernel,
            "inner_current": a.inner_score, "inner_extended": b.inner_score,
            "gain": b.inner_score - a.inner_score,
            "where": classify(b.params, base[kernel]),
            "frozen_edges": at_frozen_edge(a.params, base[kernel]),
            "n_nonconverged_extended": b.n_nonconverged,
            "params_current": a.params, "params_extended": b.params,
        })
    return out


def report(rows, kernel):
    rs = [r for r in rows if r["kernel"] == kernel]
    if not rs:
        return None
    gains = [r["gain"] for r in rs]
    moved = [r for r in rs if r["where"] != "inside"]
    print(f"\n  {kernel.upper()}  ({len(rs)} cells)")
    edges = {}
    for r in rs:
        for e in r["frozen_edges"]:
            edges[e] = edges.get(e, 0) + 1
    print(f"    frozen-grid winner sat on an edge : "
          f"{', '.join(f'{k} {v}' for k, v in sorted(edges.items())) or 'never'}")
    where = {}
    for r in moved:
        where[r["where"]] = where.get(r["where"], 0) + 1
    print(f"    winner left the frozen grid       : {len(moved)}/{len(rs)}"
          f"{'  (' + ', '.join(f'{k} {v}' for k, v in sorted(where.items())) + ')' if where else ''}")
    print(f"    inner-CV gain   mean {st.mean(gains):+.5f}   median {st.median(gains):+.5f}   "
          f"max {max(gains):+.5f}")
    if moved:
        mg = [r["gain"] for r in moved]
        print(f"    gain where it moved: mean {st.mean(mg):+.5f}   max {max(mg):+.5f}")
    by_degree = {}
    if kernel == "poly":
        for r in rs:
            deg = r["params_extended"].get("degree")
            by_degree[deg] = by_degree.get(deg, 0) + 1
        print("    winning degree on the extended grid: "
              + ", ".join(f"{k}:{v}" for k, v in sorted(by_degree.items())))
        top = max(by_degree)
        cap = max(POLY_DEGREES) + len(EXTRA_POLY_DEGREES)
        print(f"    highest winning degree {top} against an extension ceiling of {cap}"
              + ("   <-- STILL AT THE CEILING, extend further" if top >= cap else "   (clear of the ceiling)"))
        print(f"    non-converged points in the extended grid, mean per cell: "
              f"{st.mean([r['n_nonconverged_extended'] for r in rs]):.0f}")
    return {"kernel": kernel, "n": len(rs), "n_moved": len(moved), "where": where,
            "winning_degrees": by_degree,
            "frozen_edges": edges, "mean_gain": st.mean(gains),
            "median_gain": st.median(gains), "max_gain": max(gains)}


def verdict(summaries, mde, shuffled=False):
    print("\nNULL RUN SUMMARY" if shuffled else "\nVERDICT")
    worst = max((s["max_gain"] for s in summaries), default=0.0)
    mean = max((s["mean_gain"] for s in summaries), default=0.0)
    moved = max((s["n_moved"] / s["n"] for s in summaries if s["n"]), default=0.0)
    print(f"  largest gain available anywhere from widening the grid : {worst:+.5f}")
    print(f"  mean gain                                              : {mean:+.5f}")
    print(f"  winners leaving the frozen grid                        : {moved:.0%} of cells")
    if shuffled:
        print("\n  This is the NULL. Compare the real run's numbers against these, not against")
        print("  zero and not against the MDE: a maximum over a larger grid rises even when no")
        print("  point is genuinely better. Only the EXCESS over this run is evidence.")
        return
    if mde:
        ratio = worst / mde
        print(f"  minimum detectable effect for this arm                 : {mde:.4f}")
        print(f"  largest gain as a fraction of the MDE                  : {ratio:.0%}")
        if ratio < 0.33:
            print("\n  PLATEAU. The best a wider grid could buy is a fraction of the smallest")
            print("  difference this experiment can resolve, so the grid cannot be costing")
            print("  anything measurable however many edge flags it produces. Keep the frozen")
            print("  grid; raise the plateau tolerance in tuning.edge_flags so it stops")
            print("  reporting false alarms. Record both numbers in the pre-registration.")
        elif ratio < 1.0:
            print("\n  AMBIGUOUS. The gain is a noticeable fraction of the MDE. Widen the grid:")
            print("  a wider grid can only make the classical baseline harder to beat, and the")
            print("  cost is one hour of classical re-runs against a weakened claim.")
        else:
            print("\n  UNDER-TUNED. A wider grid would change the classical baseline by more")
            print("  than the effect the experiment is built to detect. Widen tuning.py's grids")
            print("  and re-run week 3 BEFORE any quantum work.")
    else:
        print("\n  Pass --mde with the minimum detectable effect for this arm (from")
        print("  scripts/power_analysis.py) to get a verdict against the experiment's own")
        print("  resolution rather than against an arbitrary threshold.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, choices=["churn", "fraud", "synthetic"])
    ap.add_argument("--seeds", type=int, nargs="+", default=SEEDS[:5])
    ap.add_argument("--mappings", nargs="+", default=list(MAPPINGS))
    ap.add_argument("--qubits", type=int, nargs="+", default=[8])
    ap.add_argument("--n-per-class", type=int, default=250)
    ap.add_argument("--direction", choices=["down", "up", "both"], default="both")
    ap.add_argument("--mde", type=float, default=None,
                    help="minimum detectable effect for this arm, from power_analysis.py")
    ap.add_argument("--jobs", type=int, default=-1)
    ap.add_argument("--shuffle-labels", action="store_true",
                    help="NULL DISTRIBUTION for the gain statistic. Extending a grid raises the "
                         "maximum inner-CV score even when no point is better than any other, "
                         "because the maximum of a noisy surface grows with the number of points "
                         "searched. On shuffled labels there is no signal, so the whole gain is "
                         "that selection noise. The real gain is only evidence of under-tuning "
                         "insofar as it EXCEEDS the shuffled gain.")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    tag = "_shuffled" if args.shuffle_labels else ""
    out_path = Path(args.out) if args.out else (
        ROOT / "results" / "analysis" / f"grid_edges_{args.dataset}_{args.direction}{tag}.json")

    X, y, _ = load_dataset(args.dataset)
    print(f"dataset={args.dataset}  seeds={args.seeds}  mappings={args.mappings}  "
          f"qubits={args.qubits}  n_per_class={args.n_per_class}  direction={args.direction}")
    if args.direction in ("down", "both"):
        print(f"  down: RBF gamma {EXTRA_RBF_LOW[0]:g}..{EXTRA_RBF_LOW[-1]:g}, "
              f"poly multiplier {EXTRA_POLY_MULT_LOW}")
    if args.direction in ("up", "both"):
        print(f"  up  : RBF gamma {EXTRA_RBF_HIGH[0]:g}..{EXTRA_RBF_HIGH[-1]:g}, "
              f"poly multiplier {EXTRA_POLY_MULT_HIGH}, poly degree {EXTRA_POLY_DEGREES}")
    print("Inner-CV scores only; no test score is read.")
    if args.shuffle_labels:
        print("NULL RUN: labels permuted. Whatever gain appears here is selection noise,")
        print("not a better hyperparameter. Subtract it from the real run's gain.")
    print()

    t0 = time.perf_counter()
    jobs = (delayed(run_cell)(X, y, s, args.n_per_class, m, q, args.direction, args.shuffle_labels)
            for s in args.seeds for m in args.mappings for q in args.qubits)
    rows = [r for batch in Parallel(n_jobs=args.jobs)(jobs) for r in batch]
    elapsed = time.perf_counter() - t0

    summaries = [s for s in (report(rows, k) for k in ("rbf", "poly")) if s]
    verdict(summaries, args.mde, args.shuffle_labels)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "dataset": args.dataset, "n_per_class": args.n_per_class, "seeds": args.seeds,
        "mappings": args.mappings, "qubits": args.qubits, "direction": args.direction,
        "mde": args.mde, "c_grid": list(C_GRID), "shuffled": bool(args.shuffle_labels),
        "extension": {"rbf_low": list(EXTRA_RBF_LOW), "rbf_high": list(EXTRA_RBF_HIGH),
                      "poly_mult_low": list(EXTRA_POLY_MULT_LOW),
                      "poly_mult_high": list(EXTRA_POLY_MULT_HIGH),
                      "poly_degrees": list(EXTRA_POLY_DEGREES)},
        "elapsed_seconds": elapsed, "summaries": summaries, "rows": rows,
    }, indent=2) + "\n")
    print(f"\nwall-clock {elapsed:.1f}s  ->  "
          f"{out_path.relative_to(ROOT) if out_path.is_relative_to(ROOT) else out_path}")


if __name__ == "__main__":
    main()
