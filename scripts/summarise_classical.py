#!/usr/bin/env python3
"""Analyse classical-baseline result files without re-running anything.

Reads results/runs/classical/<dataset>_<track>.jsonl and reports:

  1. Test PR-AUC, normalised AP and ROC-AUC per kernel, per (mapping, qubits)
     cell, and linear against the best nonlinear kernel. normAP and ROC-AUC
     are base-rate invariant and are the only two safe for cross-track or
     cross-dataset comparison.
  2. Edge flags recomputed plateau-aware from the stored grid scores, next to
     the flags recorded at run time, so the false alarms are visible.
  3. Inner-CV optimism per kernel (inner score minus outer test score) against
     grid size: how much cross-validation flatters kernels that search more
     settings.
  4. Whether the inner-CV winner is also the test winner, and what trusting it
     costs against always choosing linear.
  5. Solver health.
  6. Pairing readiness: whether per-test-point decision scores were stored and
     whether every cell in a seed was scored on the same test points.

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

from qbench.metrics import chance_average_precision, normalised_average_precision  # noqa: E402
from qbench.tuning import PLATEAU_TOL, edge_flags  # noqa: E402

KERNELS = ("linear", "rbf", "poly")

METRICS = {
    "ap": ("test PR-AUC", lambda r: r["test_average_precision"]),
    "normap": ("normalised AP", lambda r: norm_ap(r)),
    "roc": ("ROC-AUC", lambda r: r["test_roc_auc"]),
}


def norm_ap(r):
    """(AP - chance) / (1 - chance): average precision rescaled so chance is 0.

    Raw PR-AUC depends on the test base rate, so a cell at base 0.500 and a
    cell at base 0.330 cannot be compared on it. Found 22 Sep 2026: the fraud
    unconstrained track has base 0.330, because the 1000-per-class cap meets
    only 492 available positives, while the matched track is balanced at
    0.500.

    Corrected 23 Sep 2026: the chance floor is NOT the base rate. A random
    ranking of 150 test points at base 0.500 scores 0.5154, and of 30 points
    scores 0.5516 (qbench.metrics, exact). The first version of this function
    divided by (1 - base) and was therefore optimistic, most so for the
    smallest test sets -- which is exactly the training-size sweep. Use
    qbench.metrics for the real floor.
    """
    return normalised_average_precision(r["test_average_precision"],
                                        int(r["n_test"]),
                                        int(round(r["test_base_rate"] * r["n_test"])))


def load(path):
    with open(path) as f:
        return [json.loads(line) for line in f]


def recompute_flags(r, tol=PLATEAU_TOL):
    grid = [dict(p) for p in {json.dumps(g["params"], sort_keys=True): g["params"] for g in r["grid_scores"]}.values()]
    return edge_flags(r["params"], r["C"], grid, tuple(r["c_grid"]), grid_scores=r["grid_scores"], tol=tol)


def mean_sd(xs):
    return st.mean(xs), (st.stdev(xs) if len(xs) > 1 else 0.0)


def section_performance(recs):
    base = st.mean([r["test_base_rate"] for r in recs])
    n_test = recs[0]["n_test"]
    chance = chance_average_precision(int(n_test), int(round(base * n_test)))
    print(f"1. PERFORMANCE by cell (mean ± sd over seeds).  base rate {base:.3f}, "
          f"n_test {n_test}")
    print(f"   Chance AP for a RANDOM ranking here is {chance:.4f}, not the base rate "
          f"({base:.4f}).")
    print("   normAP = (AP - chance)/(1 - chance): 0 is chance, 1 is perfect. Use normAP or")
    print("   ROC-AUC for any comparison across tracks, training sizes or datasets.")
    for key in ("ap", "normap", "roc"):
        label, fn = METRICS[key]
        cells = defaultdict(lambda: defaultdict(list))
        for r in recs:
            cells[(r["mapping"], r["n_qubits"])][r["method"]].append(fn(r))
        print(f"\n   {label}")
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


def section_flags(recs, tol=PLATEAU_TOL):
    print(f"2. EDGE FLAGS: recorded at run time vs plateau-aware (tolerance {tol:g})")
    print("   DESCRIPTIVE, NOT DIAGNOSTIC. These flags say a selected value sits at a grid")
    print("   boundary. They do NOT say the grid is too narrow. Measured 24 Sep 2026 against a")
    print("   shuffled-label null, extending this grid gained +0.0016 on real churn labels and")
    print("   +0.0080 on random ones (+0.0008 against +0.0055 on fraud): widening buys more")
    print("   where there is no signal. The grid is frozen. The plateau column absorbs exact")
    print("   ties only; selection noise here (~0.008) exceeds the MDE (0.0056), so no")
    print("   tolerance can absorb the noise without hiding a detectable effect.")
    raw, fixed = defaultdict(Counter), defaultdict(Counter)
    n_raw = n_fixed = 0
    for r in recs:
        f_new = recompute_flags(r, tol)
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


def section_pairing(recs):
    """Is this run usable for week 9's paired tests, or will it need re-running?

    Two things have to hold. Every record must carry its per-test-point
    decision scores, because a paired test cannot be reconstructed from a mean.
    And every record within a seed must have been scored on the SAME test
    points in the same order, which the label fingerprint proves rather than
    assumes.
    """
    print("6. PAIRING READINESS (what week 9's statistics need from this file)")
    have = sum(1 for r in recs if r.get("test_decision_scores"))
    print(f"   records carrying per-test-point decision scores: {have}/{len(recs)}")
    if not have:
        print("   None stored. A paired test cannot be built from summary metrics, so this")
        print("   file would have to be regenerated in week 9. Re-run it now instead.\n")
        return
    by_seed = defaultdict(set)
    for r in recs:
        by_seed[r["seed"]].add(r.get("test_label_fingerprint"))
    bad = sorted(s for s, f in by_seed.items() if len(f) > 1)
    print(f"   seeds whose cells share one test-label fingerprint: {len(by_seed) - len(bad)}/{len(by_seed)}")
    if bad:
        print(f"   MISMATCH in seeds {bad}: those records were not scored on the same test")
        print("   points, so pairing them would be invalid. Diagnose before week 9.")
    print()


def resolve(in_dir, dataset, track, n_per_class, shuffled):
    """Locate the run file, tolerating both naming schemes.

    Files written before 23 Sep 2026 are <dataset>_<track>.jsonl. Since the
    training-size sweep they are <dataset>_<track>_n<size>.jsonl. Fall back to
    the old name rather than reporting 'no such file' for an archive that is
    sitting right there.
    """
    in_dir = Path(in_dir)
    suffix = "_shuffled" if shuffled else ""
    names = []
    if n_per_class is not None:
        names.append(f"{dataset}_{track}_n{n_per_class}{suffix}.jsonl")
    names.append(f"{dataset}_{track}{suffix}.jsonl")
    for name in names:
        if (in_dir / name).exists():
            return in_dir / name
    available = sorted(p.name for p in in_dir.glob(f"{dataset}_{track}*.jsonl"))
    raise SystemExit(f"none of {names} found in {in_dir}\navailable: {available or 'nothing'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--track", default="matched")
    ap.add_argument("--n-per-class", type=int, default=None,
                    help="training size to read, for sweep files written since 23 Sep 2026")
    ap.add_argument("--shuffled", action="store_true", help="read the negative-control file")
    ap.add_argument("--plateau-tol", type=float, default=PLATEAU_TOL,
                    help="two neighbouring grid points scoring within this are one plateau")
    ap.add_argument("--in-dir", default=str(ROOT / "results" / "runs" / "classical"))
    args = ap.parse_args()

    path = resolve(args.in_dir, args.dataset, args.track, args.n_per_class, args.shuffled)
    recs = load(path)
    r0 = recs[0]
    print(f"{path.name}: {len(recs)} records, {r0.get('n_seeds', len({r['seed'] for r in recs}))} seeds, "
          f"commit {r0.get('git_commit')}, C grid {r0['c_grid'][0]:g}..{r0['c_grid'][-1]:g}")
    if r0.get("shuffled"):
        print("NEGATIVE CONTROL FILE: labels were permuted. These are not results.")
    print()
    section_performance(recs)
    section_flags(recs, args.plateau_tol)
    section_optimism(recs)
    section_selection(recs)
    section_solver(recs)
    section_pairing(recs)


if __name__ == "__main__":
    main()
