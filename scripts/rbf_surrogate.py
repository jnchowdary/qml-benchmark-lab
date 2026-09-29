#!/usr/bin/env python3
"""Does the quantum kernel do anything an RBF kernel fitted to it cannot?

WHY SPEARMAN IS NOT ENOUGH, AND WHY THIS EXISTS
------------------------------------------------
`classical_limit.py` measured how close each selected quantum kernel is to its
nearest RBF. The angle family came back at Spearman 0.999999 and is settled: it
IS the classical limit. IQP came back at a median near 0.998 with a worst case
of 0.895, so it is measurably further away.

That leaves the question that actually matters unanswered. "Measurably further
from an RBF" and "does something an RBF cannot do" are not the same claim, and
a Spearman threshold cannot bridge them: nothing says 0.998 is close enough to
be the same model and 0.99 is not. Arguing about where to put that line is how
a result gets decided by the arguer.

So this script does not argue. For every quantum kernel it FITS the closest RBF
kernel, runs that RBF through the identical pipeline on the identical split, and
compares the two out-of-sample. If the surrogate scores what the quantum kernel
scores, then the quantum kernel is functionally an RBF whatever its Spearman,
and the entire quantum arm is a classical kernel reached expensively. If the
surrogate falls short, the gap is what quantum structure is worth here, measured
in the units the endpoints are measured in rather than in kernel-space distance.

THE FIT USES NO LABELS
----------------------
Gamma is chosen by least squares between two Gram matrices on the TRAINING
points only. No label, no test point and no score enters it, so the surrogate is
not tuned on the thing it is then scored on. It is nonetheless a post-hoc
kernel, so the script also reports whether each fitted gamma falls inside the
registered classical RBF grid, 1e-3 to 1e2. A surrogate that matches the quantum
kernel using a gamma the classical arm already searched is a much stronger
result than one needing a gamma nobody would have tried.

WHAT IS AND IS NOT CONCLUDED
----------------------------
Exploratory throughout, under deviations D4. No p-value from here is
confirmatory. The registered H1 and its verdict are untouched.

Usage:
    PYTHONPATH=src python scripts/rbf_surrogate.py --dataset churn
    PYTHONPATH=src python scripts/rbf_surrogate.py --all --arm bw
    PYTHONPATH=src python scripts/rbf_surrogate.py --all --arm registered
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats
from sklearn.metrics.pairwise import euclidean_distances, rbf_kernel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from qbench.data import balanced_subsample, load_dataset, make_split  # noqa: E402
from qbench.stats import rank_correlation  # noqa: E402
from qbench.features import fit_mapping, scale_to_angles  # noqa: E402
from qbench.kernels.quantum import QuantumGramFactory  # noqa: E402
from qbench.metrics import normalised_average_precision  # noqa: E402
from qbench.tuning import tune_and_evaluate  # noqa: E402
from classical_limit import FIT_GAMMAS  # noqa: E402
from primary_tests import PRIMARY_CELL, endpoint_test, fmt_p, holm  # noqa: E402

# docs/pre-registration.md section 3: the classical RBF grid actually searched.
REGISTERED_RBF_RANGE = (1e-3, 1e2)

# docs/deviations.md D2. Kernels at cond 1e16 to 1e19 give a reproducibility
# floor of roughly 1e-3 in average precision. A difference below it is not a
# small effect, it is below the arithmetic resolution of the pipeline, and D2
# commits to reporting it as such rather than as a measurement.
#
# The first version of this script ignored that and declared "the quantum kernel
# BEATS its own closest RBF" on a mean of +0.0002 with a CI spanning zero,
# because it checked only the Wilcoxon p-value and the sign. A rank test on 40
# consistently-signed but trivially small differences rejects happily. Hence the
# two extra conditions below.
PRECISION_FLOOR = 1e-3


def norm_ap_from(ap, n_test, base_rate):
    return normalised_average_precision(float(ap), int(n_test),
                                        int(round(float(base_rate) * int(n_test))))


def fit_gamma(Xa, K_q, sq=None):
    """Closest RBF by least squares on the training Gram. Labels never enter.

    The squared-distance matrix is computed once and every candidate gamma is an
    elementwise exp over it, rather than calling rbf_kernel 121 times and paying
    for the pairwise distances each time. Same answer, and it has to be: a test
    asserts the two agree. This matters because the all-cells replication below
    runs this several hundred times.
    """
    if sq is None:
        sq = euclidean_distances(Xa, squared=True)
    best, best_err = None, np.inf
    for g in FIT_GAMMAS:
        err = float(np.mean((np.exp(-float(g) * sq) - K_q) ** 2))
        if err < best_err:
            best, best_err = float(g), err
    return best, float(np.sqrt(best_err))


def one_record(dataset, cell, seed, n_per_class, qrec):
    mapping, nq = cell
    X, y, _ = load_dataset(dataset)
    Xs, ys = balanced_subsample(X, y, n_per_class=n_per_class, seed=seed)
    X_tr, X_te, y_tr, y_te = make_split(Xs, ys, seed=seed)
    Xm, transform = fit_mapping(X_tr, y_tr, nq, mapping, seed=seed)
    Xa_tr, to_angles = scale_to_angles(Xm)
    Xa_te = to_angles(transform(X_te))

    bw = float(qrec.get("bandwidth", 1.0))
    params = {"embedding": qrec["embedding"], "reps": int(qrec["reps"]), "bandwidth": bw}
    K_q = QuantumGramFactory(nq).gram_fn(params)(Xa_tr)
    gamma, rmse = fit_gamma(Xa_tr, K_q)

    # The surrogate goes through the SAME function, with the same C grid, folds
    # and selection rule. Only the Gram differs, which is the property that makes
    # the comparison a like-for-like one.
    sur = tune_and_evaluate(
        f"rbf-surrogate-g{gamma:.3e}",
        lambda p: (lambda A, B=None: rbf_kernel(A, A if B is None else B, gamma=gamma)),
        [{}], Xa_tr, y_tr, Xa_te, y_te, seed=seed)

    if sur["test_label_fingerprint"] != qrec["test_label_fingerprint"]:
        raise SystemExit(f"HALT: surrogate for seed {seed} was scored on different "
                         f"test points than the quantum record. Not comparable.")

    q_nap = norm_ap_from(qrec["test_average_precision"], qrec["n_test"],
                         qrec["test_base_rate"])
    s_nap = norm_ap_from(sur["test_average_precision"], sur["n_test"],
                         sur["test_base_rate"])
    lo, hi = REGISTERED_RBF_RANGE
    return {"seed": seed, "setting": qrec["setting"], "embedding": qrec["embedding"],
            "n_qubits": int(qrec["n_qubits"]), "mapping": qrec["mapping"],
            "bandwidth": bw, "gamma": gamma, "gram_rmse": rmse,
            "in_registered_rbf_range": bool(lo <= gamma <= hi),
            "quantum_normap": q_nap, "surrogate_normap": s_nap,
            "d_normap": q_nap - s_nap,
            "quantum_roc": float(qrec["test_roc_auc"]),
            "surrogate_roc": float(sur["test_roc_auc"]),
            "d_roc": float(qrec["test_roc_auc"]) - float(sur["test_roc_auc"])}


def report(dataset, n_per_class, arm, q_dir, seeds, settings, cell=None):
    cell = cell or PRIMARY_CELL[dataset]
    suffix = "_bw" if arm == "bw" else ""
    path = q_dir / f"{dataset}_matched_n{n_per_class}{suffix}.jsonl"
    if not path.exists():
        print(f"\nmissing {path.name}")
        return None
    recs = [json.loads(l) for l in path.open() if l.strip()]
    recs = [r for r in recs if (r["mapping"], r["n_qubits"]) == cell
            and r["seed"] < seeds and (not settings or r["setting"] in settings)]
    if not recs:
        print(f"\nno records for {dataset} in {cell}")
        return None

    print(f"\n{'=' * 74}")
    print(f"RBF SURROGATE (EXPLORATORY, D4): {dataset}, {cell[0]}/{cell[1]} qubits, "
          f"{n_per_class}/class, {arm} arm")
    print(f"{'=' * 74}")
    print("  For each quantum kernel: fit the closest RBF on training Gram matrices")
    print("  (no labels), run it through the same pipeline, compare out of sample.")
    print("  A difference near zero means the quantum kernel is functionally that RBF.\n")

    rows = [one_record(dataset, cell, r["seed"], n_per_class, r)
            for r in sorted(recs, key=lambda r: (r["setting"], r["seed"]))]

    by_setting = defaultdict(list)
    for r in rows:
        by_setting[r["setting"]].append(r)

    print(f"  REAL marks an effect that clears all three conditions: rank test rejects,")
    print(f"  interval excludes zero, and |effect| exceeds the {PRECISION_FLOOR:g} "
          f"precision floor of D2.\n")
    print(f"  {'setting':<10} {'n':>3} {'gamma (median)':>15} {'in grid':>8} "
          f"{'d normAP':>11} {'95% CI':>22} {'p':>10} {'':>5}")
    out = []
    for setting in sorted(by_setting):
        rs = by_setting[setting]
        e = endpoint_test([r["d_normap"] for r in rs])
        ing = sum(r["in_registered_rbf_range"] for r in rs)
        ci = f"[{e['ci'][0]:+.4f}, {e['ci'][1]:+.4f}]" if e["n"] > 1 else "-"
        ok, _ = _significant(e)
        print(f"  {setting:<10} {len(rs):>3} {np.median([r['gamma'] for r in rs]):>15.3e} "
              f"{ing}/{len(rs):<6} {e['mean']:>+11.4f} {ci:>22} "
              f"{fmt_p(e['p_wilcoxon']):>10} {'REAL' if ok else '':>5}")
        out.append({"setting": setting, "embedding": rs[0]["embedding"],
                    "n": len(rs), "gamma_median": float(np.median([r["gamma"] for r in rs])),
                    "in_registered_rbf_range": ing, "normap": e,
                    "roc": endpoint_test([r["d_roc"] for r in rs])})

    print(f"\n  By embedding family:")
    for fam in sorted({r["embedding"] for r in rows}):
        rs = [r for r in rows if r["embedding"] == fam]
        e = endpoint_test([r["d_normap"] for r in rs])
        fam_settings = [s for s in out if s["embedding"] == fam]
        print(f"    {fam:<6} n={len(rs):<3} quantum minus surrogate: {e['mean']:+.4f} "
              f"[{e['ci'][0]:+.4f}, {e['ci'][1]:+.4f}]   p {fmt_p(e['p_wilcoxon'])}")
        print(f"           {_reading(fam, e, fam_settings)}")

    allg = [r["gamma"] for r in rows]
    outside = [g for g in allg if not (REGISTERED_RBF_RANGE[0] <= g <= REGISTERED_RBF_RANGE[1])]
    print(f"\n  Fitted gammas span {min(allg):.2e} to {max(allg):.2e}; the registered "
          f"classical RBF grid spans {REGISTERED_RBF_RANGE[0]:.0e} to "
          f"{REGISTERED_RBF_RANGE[1]:.0e}.")
    print(f"  {len(allg) - len(outside)}/{len(allg)} surrogates use a gamma inside the "
          f"range the classical arm already searched"
          f"{'' if not outside else f'; {len(outside)} do not'}.")

    return {"dataset": dataset, "n_per_class": n_per_class, "arm": arm,
            "cell": list(cell), "per_setting": out, "rows": rows,
            "confirmatory": False}


def _significant(e):
    """Three conditions, all required, none of them sufficient alone.

    1. The rank test rejects. On its own this says only that the differences are
       consistently signed, which trivially small differences can be.
    2. The confidence interval excludes zero. The CI is t-based and the p-value
       is Wilcoxon, so requiring both is deliberately conservative: where the two
       disagree, the disagreement is the finding.
    3. The effect clears the pipeline's own precision floor (D2). Below it the
       number is not reproducible, so it cannot be a result.
    """
    if e["n"] < 2 or not np.isfinite(e["ci"][0]):
        return False, "too few records"
    p_ok = e["p_wilcoxon"] < 0.05
    ci_ok = (e["ci"][0] > 0) or (e["ci"][1] < 0)
    floor_ok = abs(e["mean"]) > PRECISION_FLOOR
    if not floor_ok:
        return False, (f"|effect| {abs(e['mean']):.4f} is below the {PRECISION_FLOOR:g} "
                       f"precision floor (D2): not a measurement")
    if p_ok and not ci_ok:
        return False, ("rank test rejects but the interval spans zero: consistently "
                       "signed and too small to matter")
    if ci_ok and not p_ok:
        return False, "interval excludes zero but the rank test does not reject"
    if not p_ok:
        return False, "no detectable difference"
    return True, ""


def _heterogeneous(per_setting):
    """Do the settings inside this family disagree beyond overlap?

    Averaging iqp-r1 at +0.0852 [+0.0645, +0.1058] with iqp-r2 at -0.0493
    [-0.0913, -0.0072] gives +0.0180 and a family verdict of 'no detectable
    difference', which is true of neither setting. Non-overlapping intervals
    mean the family has no common effect to report.
    """
    cis = [(s["normap"]["ci"][0], s["normap"]["ci"][1]) for s in per_setting
           if s["normap"]["n"] > 1 and np.isfinite(s["normap"]["ci"][0])]
    for i, a in enumerate(cis):
        for b in cis[i + 1:]:
            if a[1] < b[0] or b[1] < a[0]:
                return True
    return False


def _reading(fam, e, per_setting):
    if _heterogeneous(per_setting):
        return ("settings inside this family have non-overlapping intervals, so there "
                "is no family-level effect to report. Read the per-setting rows above; "
                "the average of opposite effects is not one of them.")
    ok, why = _significant(e)
    lo, hi = e["ci"]
    if not ok:
        if "precision floor" in why or "too small" in why:
            return (f"{why}. Quantum and surrogate are indistinguishable at the "
                    f"resolution this pipeline can resolve.")
        return (f"{why}; interval [{lo:+.4f}, {hi:+.4f}]. "
                + ("tight enough to exclude an effect of the size seen elsewhere."
                   if (hi - lo) < 0.05 else
                   "too wide to conclude equivalence: absence of evidence."))
    if e["mean"] > 0:
        return (f"the quantum kernel beats its own closest RBF by {e['mean']:+.4f}, "
                f"above the precision floor with an interval clear of zero. This says "
                f"the kernel is NOT functionally an RBF. It does NOT say it beats the "
                f"best classical kernel, which is a separate number.")
    return (f"the quantum kernel is worse than its own closest RBF by {e['mean']:+.4f}: "
            f"its structure costs rather than earns, and it is not an RBF either.")


def report_all_cells(dataset, n_per_class, arm, q_dir, seeds, settings):
    """Does the primary cell's effect replicate anywhere else?

    The registered arm on churn produced one large positive surrogate gap,
    iqp-r1 at +0.0852. It came from one cell on one dataset and nothing has
    replicated it. Fourteen other cells are already on disk, so the cheapest
    possible check is to ask all of them the same question.

    Holm-corrected across cells within each setting, and exploratory throughout:
    a cell that survives correction here is a replication, not a hypothesis test.
    """
    suffix = "_bw" if arm == "bw" else ""
    path = q_dir / f"{dataset}_matched_n{n_per_class}{suffix}.jsonl"
    if not path.exists():
        print(f"\nmissing {path.name}")
        return None
    recs = [json.loads(l) for l in path.open() if l.strip()]
    recs = [r for r in recs if r["seed"] < seeds
            and (not settings or r["setting"] in settings)]
    cells = sorted({(r["mapping"], r["n_qubits"]) for r in recs})
    primary = PRIMARY_CELL[dataset]

    print(f"\n{'=' * 78}")
    print(f"REPLICATION ACROSS CELLS (EXPLORATORY, D4): {dataset}, {n_per_class}/class, "
          f"{arm} arm")
    print(f"{'=' * 78}")
    print(f"  settings: {settings or 'all'}   cells: {len(cells)}   "
          f"primary: {primary[0]}/{primary[1]}")
    print(f"  Question: does the primary cell's surrogate gap appear anywhere else?\n")

    per_setting = defaultdict(list)
    for cell in cells:
        sel = [r for r in recs if (r["mapping"], r["n_qubits"]) == cell]
        rows = [one_record(dataset, cell, r["seed"], n_per_class, r) for r in sel]
        for setting in sorted({r["setting"] for r in rows}):
            rs_ = [r for r in rows if r["setting"] == setting]
            if len(rs_) < 2:
                continue
            per_setting[setting].append({
                "cell": cell, "n": len(rs_), "rows": rs_,
                "gamma_median": float(np.median([r["gamma"] for r in rs_])),
                "e": endpoint_test([r["d_normap"] for r in rs_])})

    out = []
    for setting, entries in sorted(per_setting.items()):
        praw = [x["e"]["p_wilcoxon"] for x in entries]
        adj = holm(praw)
        print(f"  --- {setting} ---")
        print(f"  {'cell':<15} {'gamma':>10} {'d normAP':>11} {'95% CI':>22} "
              f"{'p':>10} {'Holm':>10} {'':>5}")
        reps = 0
        for x, pa in sorted(zip(entries, adj), key=lambda z: -z[0]["e"]["mean"]):
            ok, _ = rs_significant_with_holm(x["e"], pa)
            reps += bool(ok)
            mark = "REAL" if ok else ""
            star = " <- primary" if x["cell"] == primary else ""
            print(f"  {x['cell'][0] + '/' + str(x['cell'][1]):<15} "
                  f"{x['gamma_median']:>10.2e} {x['e']['mean']:>+11.4f} "
                  f"[{x['e']['ci'][0]:+.4f}, {x['e']['ci'][1]:+.4f}] "
                  f"{fmt_p(x['e']['p_wilcoxon']):>10} {fmt_p(pa):>10} {mark:>5}{star}")
        pos = [x for x, pa in zip(entries, adj)
               if rs_significant_with_holm(x["e"], pa)[0] and x["e"]["mean"] > 0]
        neg = [x for x, pa in zip(entries, adj)
               if rs_significant_with_holm(x["e"], pa)[0] and x["e"]["mean"] < 0]
        flat = [r for x in entries for r in x["rows"]]
        t = trend_stats(entries, flat)
        print_trend(setting, t)
        print(f"    {reps}/{len(entries)} cells clear all three conditions after Holm: "
              f"{len(pos)} positive, {len(neg)} negative")
        print(f"    {_replication_reading(setting, entries, adj, primary, pos, neg)}\n")
        out.append({"setting": setting, "n_cells": len(entries), "trend": t,
                    "n_real": reps, "n_positive": len(pos), "n_negative": len(neg),
                    "cells": [{"cell": list(x["cell"]), "mean": x["e"]["mean"],
                               "ci": list(x["e"]["ci"]), "p": x["e"]["p_wilcoxon"],
                               "holm": pa, "gamma": x["gamma_median"]}
                              for x, pa in zip(entries, adj)]})
    return {"dataset": dataset, "n_per_class": n_per_class, "arm": arm,
            "mode": "all_cells", "per_setting": out, "confirmatory": False}


def trend_stats(entries, rows):
    """Spearman of the gap against qubit count and against fitted gamma, computed
    over CELLS, plus the absolute levels of both arms by qubit count.

    The unit of analysis is the cell, n = 15, not the individual record, n = 300.
    Twenty records inside one cell are twenty seeds of the same configuration and
    are not twenty independent observations of the trend; seeds are also paired
    across cells by construction. The first version of this function correlated
    over rows and reported fraud angle-r2 at rho = -0.149 with p = 0.0099, on a
    column where every gap sat at or below the 1e-3 precision floor of D2. That is
    significance manufactured by row count.

    The absolute levels below stay at row granularity because they are means, not
    tests, and the cells are balanced across qubit counts.

    The absolute levels are here for one reason. The gap is quantum minus
    surrogate, and at higher qubit counts the quantum kernel concentrates, so its
    best-fit RBF has larger gamma and is a worse classifier. A gap that grows with
    qubits could therefore mean the SURROGATE is degrading rather than the quantum
    kernel improving, and those two readings have opposite consequences. Printing
    both levels is the only way to tell them apart, and it is cheap.
    """
    q = [x["cell"][1] for x in entries]
    g = [x["gamma_median"] for x in entries]
    d = [x["e"]["mean"] for x in entries]
    # `g` was NOT in this guard, so rq was protected and rg was not: a constant
    # gamma_median gave spearman_gamma = [nan, nan] in the report JSON and a
    # ConstantInputWarning on every test run. The helper checks both inputs of
    # both correlations, so the asymmetry cannot recur.
    if len(set(q)) < 2 or len(set(d)) < 2:
        return None
    rq = rank_correlation(q, d)
    rg = rank_correlation(g, d)
    by_q = {}
    for nq in sorted(set(q), reverse=True):
        sel = [r for r in rows if r["n_qubits"] == nq]
        by_q[nq] = {"gap": float(np.mean([r["d_normap"] for r in sel])),
                    "quantum": float(np.mean([r["quantum_normap"] for r in sel])),
                    "surrogate": float(np.mean([r["surrogate_normap"] for r in sel])),
                    "gamma": float(np.median([r["gamma"] for r in sel])),
                    "n": len(sel)}
    small = [x["e"]["mean"] for x in entries if x["gamma_median"] < 0.2]
    big = [x["e"]["mean"] for x in entries if x["gamma_median"] >= 0.2]
    return {"n_cells": len(entries), "n_records": len(rows),
            "spearman_qubits": ([rq.rho, rq.p] if rq.ok else None),
            "spearman_qubits_why": (None if rq.ok else rq.why),
            "spearman_gamma": ([rg.rho, rg.p] if rg.ok else None),
            "spearman_gamma_why": (None if rg.ok else rg.why),
            "by_qubits": by_q,
            "gamma_below_0.2": {"n": len(small),
                                "mean": float(np.mean(small)) if small else None},
            "gamma_at_or_above_0.2": {"n": len(big),
                                      "mean": float(np.mean(big)) if big else None}}


def print_trend(setting, t):
    if t is None:
        print("    (only one qubit count present; no trend to report)")
        return
    rq, pq = t["spearman_qubits"]
    rg, pg = t["spearman_gamma"]
    print(f"    trend over {t['n_cells']} CELLS (not {t['n_records']} records: seeds "
          f"within a cell are not independent observations of a trend)")
    print(f"      Spearman(qubits, gap) {rq:+.3f} p {fmt_p(pq)}   |   "
          f"Spearman(gamma, gap) {rg:+.3f} p {fmt_p(pg)}")
    print(f"    {'qubits':>7} {'n':>3} {'gap':>9} {'quantum':>9} {'surrogate':>10} {'gamma':>9}")
    for nq, v in t["by_qubits"].items():
        print(f"    {nq:>7} {v['n']:>3} {v['gap']:>+9.4f} {v['quantum']:>9.4f} "
              f"{v['surrogate']:>10.4f} {v['gamma']:>9.2e}")
    print("    Read the last three columns together: a gap that grows while the")
    print("    surrogate column falls and the quantum column is flat means the")
    print("    comparator degraded, not that the quantum kernel improved.")
    sm, bg = t["gamma_below_0.2"], t["gamma_at_or_above_0.2"]
    if sm["n"]:
        print(f"    gamma < 0.2: n={sm['n']} mean gap {sm['mean']:+.4f}   |   "
              f"gamma >= 0.2: n={bg['n']} mean gap {bg['mean']:+.4f}")
    else:
        print(f"    gamma < 0.2: none in this arm, so any prediction conditioned on "
              f"small gamma is untestable here, not passed.")


def rs_significant_with_holm(e, p_adj):
    """The three conditions, with the Holm-corrected p in place of the raw one."""
    ok, why = _significant(e)
    if not ok:
        return False, why
    if p_adj >= 0.05:
        return False, f"does not survive Holm across cells (adjusted p {p_adj:.3f})"
    return True, ""


def _replication_reading(setting, entries, adj, primary, pos, neg):
    prim = next((x for x in entries if x["cell"] == primary), None)
    if prim is None:
        return "the primary cell is not in this run, so replication cannot be judged."
    prim_ok, _ = _significant(prim["e"])
    if not prim_ok:
        return ("the primary cell itself does not clear the three conditions for this "
                "setting, so there is nothing here to replicate.")
    same_sign = [x for x in (pos if prim["e"]["mean"] > 0 else neg)
                 if x["cell"] != primary]
    if not same_sign:
        return ("the primary cell's effect appears in NO other cell. One cell out of "
                f"{len(entries)} is a single observation, not a finding, and it must be "
                "reported as unreplicated or dropped.")
    if len(same_sign) + 1 >= len(entries) / 2:
        return (f"the effect replicates in {len(same_sign)} further cells of "
                f"{len(entries) - 1}, same sign, after Holm. That is a property of the "
                f"kernel rather than of one cell.")
    return (f"the effect replicates in {len(same_sign)} of {len(entries) - 1} further "
            f"cells. Partial replication: report the count, and look for what "
            f"distinguishes the cells where it appears.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=sorted(PRIMARY_CELL))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--arm", choices=["bw", "registered"], default="bw",
                    help="bw: the bandwidth-tuned arm. registered: the frozen grid.")
    ap.add_argument("--n-per-class", type=int, default=250)
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--all-cells", action="store_true",
                    help="run every cell, not just the primary one, and Holm-correct "
                         "across cells. This is the replication check; restrict "
                         "--settings to keep it affordable.")
    ap.add_argument("--settings", nargs="*", default=None,
                    help="restrict to these settings, e.g. iqp-r1 iqp-r2")
    ap.add_argument("--quantum-dir", default=str(ROOT / "results" / "runs" / "quantum"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if not args.all and not args.dataset:
        ap.error("give --dataset or --all")
    if args.out is None:
        # Dataset and training size MUST be in the name. The first version left
        # them out, so three all-cells runs in one command overwrote each other
        # and only the tee logs survived. Scoring then had to be done by
        # transcribing rows out of a log by hand, which is not a method.
        who = args.dataset if not args.all else "all"
        tag = (f"{who}_n{args.n_per_class}_{args.arm}"
               + ("_allcells" if args.all_cells else ""))
        args.out = str(ROOT / "results" / "analysis" / f"rbf_surrogate_{tag}.json")

    print("A kernel that scores what its nearest RBF scores is that RBF, whatever its")
    print("Spearman. Exploratory under deviations D4; nothing here is confirmatory.")

    jobs = sorted(PRIMARY_CELL) if args.all else [args.dataset]
    fn = report_all_cells if args.all_cells else report
    out = [r for r in (fn(d, args.n_per_class, args.arm, Path(args.quantum_dir),
                          args.seeds, args.settings) for d in jobs) if r]
    if out:
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"exploratory": True, "deviation": "D4",
                                 "results": out}, indent=2, default=float) + "\n")
        print(f"\n-> {p.relative_to(ROOT) if p.is_relative_to(ROOT) else p}")


if __name__ == "__main__":
    main()
