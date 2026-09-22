#!/usr/bin/env python3
"""Analyse classical-baseline result files without re-running anything.

Reads results/runs/classical/<dataset>_<track>.jsonl and reports:

  1. Test PR-AUC per kernel, per (mapping, qubits) cell, and linear against
     the best nonlinear kernel.
  2. Edge flags recomputed plateau-aware from the stored grid scores, next to
     the flags recorded at run time, so the false alarms are visible.
  3. Inner-CV optimism per kernel (inner score minus outer test score) against
     grid size: how much cross-validation flatters kernels that search more
     settings.
  4. Whether the inner-CV winner is also the test winner, and what trusting it
     costs against always choosing linear.

Outer test scores are used here ONLY for after-the-fact diagnosis. No grid,
selection rule or reference-kernel choice may be changed on the strength of
sections 3 and 4 without saying so explicitly in the write-up.

Usage:
    PYTHONPATH=src python scripts/summarise_classical.py --dataset churn --track matched
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qbench.tuning import edge_flags  # noqa: E402

KERNELS = ("linear", "rbf", "poly")


def load(path):
    with open(path) as f:
        return [json.loads(line) for line in f]


def recompute_flags(r):
    grid = [dict(p) for p in {json.dumps(g["params"], sort_keys=True): g["params"] for g in r["grid_scores"]}.values()]
    return edge_flags(r["params"], r["C"], grid, tuple(r["c_grid"]), grid_scores=r["grid_scores"])


def mean_sd(xs):
    return st.mean(xs), (st.stdev(xs) if len(xs) > 1 else 0.0)


def section_performance(recs):
    print("1. TEST PR-AUC by cell (mean ± sd over seeds)")
    cells = defaultdict(lambda: defaultdict(list))
    for r in recs:
        cells[(r["mapping"], r["n_qubits"])][r["method"]].append(r["test_average_precision"])
    print(f"   {'mapping':<10}{'qubits':>7}{'linear':>17}{'rbf':>17}{'poly':>17}{'lin - best nonlin':>20}")
    for (mapping, nq), by in sorted(cells.items(), key=lambda kv: (kv[0][0], kv[0][1] or 0)):
        cols = []
        for k in KERNELS:
            m, s = mean_sd(by[k]) if by[k] else (float("nan"), 0.0)
            cols.append(f"{m:.4f} ± {s:.3f}")
        lin = st.mean(by["linear"])
        best_nl = max(st.mean(by["rbf"]), st.mean(by["poly"]))
        q = "-" if nq is None else str(nq)
        print(f"   {mapping:<10}{q:>7}" + "".join(f"{c:>17}" for c in cols) + f"{lin - best_nl:>+20.4f}")
    print()


def section_flags(recs):
    print("2. EDGE FLAGS: recorded at run time vs plateau-aware")
    raw, fixed = defaultdict(Counter), defaultdict(Counter)
    n_raw = n_fixed = 0
    for r in recs:
        f_new = recompute_flags(r)
        n_raw += bool(r["edge"])
        n_fixed += bool(f_new)
        for f in r["edge"]:
            raw[r["method"]][f.split("=")[0] + " " + f.split("(")[-1].rstrip(")").replace("grid ", "")] += 1
        for f in f_new:
            fixed[r["method"]][f.split("=")[0] + " " + f.split("(")[-1].rstrip(")").replace("grid ", "")] += 1
    print(f"   models with any flag: {n_raw} recorded -> {n_fixed} after removing plateaus (of {len(recs)})")
    for k in KERNELS:
        keys = sorted(set(raw[k]) | set(fixed[k]))
        detail = ", ".join(f"{key} {raw[k][key]}->{fixed[k][key]}" for key in keys) or "none"
        print(f"   {k:<7} {detail}")
    print()


def section_optimism(recs):
    print("3. INNER-CV OPTIMISM (inner score minus outer test score)")
    opt, size = defaultdict(list), {}
    for r in recs:
        opt[r["method"]].append(r["inner_score"] - r["test_average_precision"])
        size[r["method"]] = len(r["grid_scores"])
    for k in KERNELS:
        m, s = mean_sd(opt[k])
        print(f"   {k:<7} grid size {size[k]:>4}   mean optimism {m:+.4f}  (sd {s:.4f})")
    print("   If optimism rises with grid size, cross-validation is flattering the kernels that")
    print("   search more settings, and inner-CV scores must not be used to rank kernels.\n")


def section_selection(recs):
    print("4. DOES THE INNER-CV WINNER WIN ON TEST?")
    cells = defaultdict(dict)
    for r in recs:
        cells[(r["mapping"], r["n_qubits"], r["seed"])][r["method"]] = r
    hits, regret, lin, win = 0, [], [], []
    winners = Counter()
    for rs in cells.values():
        by_inner = max(rs.values(), key=lambda r: r["inner_score"])
        by_test = max(rs.values(), key=lambda r: r["test_average_precision"])
        winners[by_inner["method"]] += 1
        hits += by_inner["method"] == by_test["method"]
        regret.append(by_test["test_average_precision"] - by_inner["test_average_precision"])
        lin.append(rs["linear"]["test_average_precision"])
        win.append(by_inner["test_average_precision"])
    n = len(cells)
    print(f"   inner-CV winners: {dict(winners)}")
    print(f"   inner winner = test winner in {hits}/{n} cells ({100 * hits / n:.0f}%; chance {100 / len(KERNELS):.0f}%)")
    print(f"   test PR-AUC: always-linear {st.mean(lin):.4f}  vs  inner-CV winner {st.mean(win):.4f}  "
          f"(difference {st.mean(win) - st.mean(lin):+.4f})\n")


def section_solver(recs):
    bad = Counter()
    for r in recs:
        bad[r["method"]] += r["n_nonconverged"]
    fb = sum(1 for r in recs if r.get("final_fallback_rank", 0) > 0)
    nf = sum(1 for r in recs if not r["final_converged"])
    print("5. SOLVER")
    print(f"   non-converged inner fits by kernel: {dict(bad)}")
    print(f"   final-fit fallbacks: {fb};  final models not converged: {nf}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--track", default="matched")
    ap.add_argument("--in-dir", default=str(ROOT / "results" / "runs" / "classical"))
    args = ap.parse_args()

    path = Path(args.in_dir) / f"{args.dataset}_{args.track}.jsonl"
    recs = load(path)
    r0 = recs[0]
    print(f"{path.name}: {len(recs)} records, commit {r0.get('git_commit')}, C grid {r0['c_grid'][0]:g}..{r0['c_grid'][-1]:g}\n")
    section_performance(recs)
    section_flags(recs)
    section_optimism(recs)
    section_selection(recs)
    section_solver(recs)


if __name__ == "__main__":
    main()
