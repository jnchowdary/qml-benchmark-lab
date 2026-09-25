#!/usr/bin/env python3
"""Did tuning the bandwidth make the quantum kernel work, or make it classical?

THE PROBLEM THIS EXISTS TO SETTLE
---------------------------------
Tuning bandwidth closed the churn gap: normAP -0.0798 (p 8.2e-05) became
-0.0101 (p 0.076), and iqp-r2 went from -0.3008 to +0.0114. Nineteen of twenty
seeds chose a bandwidth BELOW the registered 1.0, and thirty-seven of eighty
records chose the grid's lowest value, 0.0625.

That direction is not neutral. For the angle family the small-bandwidth limit of
a fidelity kernel is a classical Gaussian kernel, analytically:

    K_ij = prod_d cos^2(b * (x_d - y_d) / 2)
    log K_ij = sum_d 2 log cos(b * Delta_d / 2)
             ~= -(b^2 / 4) * ||x - y||^2          for small b * Delta
    so  K -> exp(-gamma ||x - y||^2)  with  gamma = (reps * b)^2 / 4

At b = 0.0625 that is gamma = 9.8e-4, which is essentially 1e-3, the BOTTOM of
the classical RBF grid this project has been searching since week 2. At
b = 0.125 it is 3.9e-3. So the bandwidths inner CV selected are exactly the
region where the quantum kernel stops being distinguishable from a kernel the
classical arm already had.

If that is what happened, then "bandwidth fixes the quantum kernel" means "the
quantum kernel performs acceptably once it is allowed to become classical",
which is the opposite of an advantage and must be reported as such. This script
measures it instead of arguing it.

WHAT IS MEASURED, PER SEED, IN THE PRIMARY CELL
-----------------------------------------------
1. Agreement between the selected quantum Gram and the RBF Gram at the
   predicted gamma = (reps*b)^2/4: maximum absolute difference, and Spearman
   correlation of the off-diagonals. Spearman as well as the raw difference
   because the SVM is rank-driven (see deviations D2): two kernels that induce
   the same ordering are the same kernel as far as both registered endpoints
   are concerned.
2. The empirical best-fit gamma, found by least squares, against the predicted
   one. Agreement of the fit with the prediction is the check that the
   derivation above is the right explanation and not a coincidence.
3. Concentration, which is the mechanism on the other side: mean and relative
   spread of the off-diagonal Gram entries at the selected bandwidth and at the
   registered 1.0. Concentration toward 2^-n is what made the registered kernel
   fail; concentration toward all-ones is what makes a tiny bandwidth trivial.
4. g_lambda(K_C || K_Q) at both bandwidths, as a preview of week 5. If g is near
   1 at the selected bandwidth and large at the registered one, then g is
   reporting exactly what Huang et al. claim it reports, and the useful finding
   is that the only bandwidths where this quantum kernel competes are the ones
   where g says no advantage is available.

The IQP family has a different small-b limit, since its repetitions carry
entangling ZZ terms, so the analytic gamma is reported only for the angle
family. The empirical fit is reported for both.

CAVEAT ON g
-----------
Section 6 of the pre-registration specifies the reference classical kernel for
g by kernel-target alignment, while lambda is tied to the C that inner CV
selected. This script uses the inner-CV-selected classical kernel for both and
labels the result a preview. Settling that is week 5's job and is not to be
decided here by whichever choice this script happened to make.

Usage:
    PYTHONPATH=src python scripts/classical_limit.py --dataset churn
    PYTHONPATH=src python scripts/classical_limit.py --all
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import stats
from sklearn.metrics.pairwise import rbf_kernel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from qbench.data import balanced_subsample, load_dataset, make_split  # noqa: E402
from qbench.features import fit_mapping, scale_to_angles  # noqa: E402
from qbench.kernels.classical import build_classical_kernel  # noqa: E402
from qbench.kernels.geometric_difference import (  # noqa: E402
    geometric_difference_regularised,
    lambda_from_svm_C,
)
from qbench.kernels.quantum import QuantumGramFactory  # noqa: E402
from primary_tests import PRIMARY_CELL, best_by_inner  # noqa: E402

# Fine grid for the empirical fit. Deliberately much finer than anything the
# experiment searched: this is a measurement of what the kernel IS, not a
# hyperparameter search, and nothing downstream selects on it.
FIT_GAMMAS = np.concatenate([np.logspace(-5, 1, 121)])

# Section 6 promises a lambda sweep beside every g. That is not decoration. g is
# computed from (K_C + lam*I)^-2, so a classical model at the top of the C grid
# gives lam = 1/(2*C*n) ~ 1e-7 and g diverges: the first run of this script
# returned g = 57.3, against a sqrt(n) ceiling of 18.71, for a kernel that agreed
# with an RBF to 2.4e-05. A g above its ceiling says the classical kernel is
# under-regularised in the g computation, NOT that the quantum kernel separates.
LAMBDA_SWEEP = (1e-1, 1e-2, 1e-3, 1e-4)


def predicted_gamma(reps: int, bandwidth: float) -> float:
    return (reps * bandwidth) ** 2 / 4.0


def offdiag(K):
    n = len(K)
    return K[~np.eye(n, dtype=bool)]


def fit_gamma(Xa, K_q):
    """Least-squares closest RBF kernel over a fine gamma grid."""
    best, best_err = None, np.inf
    for g in FIT_GAMMAS:
        err = float(np.mean((rbf_kernel(Xa, gamma=float(g)) - K_q) ** 2))
        if err < best_err:
            best, best_err = float(g), err
    return best, float(np.sqrt(best_err))


def concentration(K, n_qubits):
    od = offdiag(K)
    mean = float(od.mean())
    return {"mean_offdiag": mean,
            "sd_offdiag": float(od.std()),
            "relative_spread": float(od.std() / mean) if mean > 0 else float("nan"),
            "haar_floor": 2.0 ** (-int(n_qubits))}


def one_seed(dataset, cell, seed, n_per_class, qrec, crec):
    mapping, nq = cell
    X, y, _ = load_dataset(dataset)
    Xs, ys = balanced_subsample(X, y, n_per_class=n_per_class, seed=seed)
    X_tr, X_te, y_tr, y_te = make_split(Xs, ys, seed=seed)
    Xm, transform = fit_mapping(X_tr, y_tr, nq, mapping, seed=seed)
    Xa_tr, _ = scale_to_angles(Xm)

    bw = float(qrec.get("bandwidth", 1.0))
    reps = int(qrec["reps"])
    params = {"embedding": qrec["embedding"], "reps": reps}
    factory = QuantumGramFactory(nq)

    K_sel = factory.gram_fn({**params, "bandwidth": bw})(Xa_tr)
    K_reg = factory.gram_fn({**params, "bandwidth": 1.0})(Xa_tr)

    g_pred = predicted_gamma(reps, bw)
    K_rbf = rbf_kernel(Xa_tr, gamma=g_pred)
    g_fit, fit_rmse = fit_gamma(Xa_tr, K_sel)

    rho = float(stats.spearmanr(offdiag(K_sel), offdiag(K_rbf)).statistic)
    # Against each row's OWN nearest RBF, which is the fair question for IQP:
    # "is this kernel some RBF", not "is it the angle-limit RBF".
    K_fit = rbf_kernel(Xa_tr, gamma=g_fit)
    rho_fit = float(stats.spearmanr(offdiag(K_sel), offdiag(K_fit)).statistic)

    # g against the classical kernel inner CV actually chose for this cell.
    cparams = {k: v for k, v in (crec.get("params") or {}).items()}
    K_c = build_classical_kernel(crec["method"], **cparams)(Xa_tr)
    lam = lambda_from_svm_C(float(crec["C"]), len(y_tr))
    g_sel = geometric_difference_regularised(K_c, K_sel, lam=lam, warn_above_ceiling=False)
    g_registered = geometric_difference_regularised(K_c, K_reg, lam=lam, warn_above_ceiling=False)
    # The sweep section 6 promises. Without it a single g is uninterpretable,
    # because lam from a top-of-grid C is small enough to make g diverge.
    sweep = {f"{l:g}": {
        "selected": geometric_difference_regularised(K_c, K_sel, lam=l,
                                                     warn_above_ceiling=False),
        "registered": geometric_difference_regularised(K_c, K_reg, lam=l,
                                                       warn_above_ceiling=False)}
        for l in LAMBDA_SWEEP}

    return {
        "seed": seed, "setting": qrec["setting"], "embedding": qrec["embedding"],
        "reps": reps, "bandwidth": bw,
        "gamma_predicted": g_pred, "gamma_fitted": g_fit,
        "gamma_ratio": (g_fit / g_pred) if g_pred > 0 else float("nan"),
        "max_abs_diff_vs_predicted_rbf": float(np.abs(K_sel - K_rbf).max()),
        "rmse_best_fit_rbf": fit_rmse,
        "spearman_offdiag_vs_predicted_rbf": rho,
        "spearman_offdiag_vs_best_fit": rho_fit,
        "C_classical": float(crec["C"]),
        "g_lambda_sweep": sweep,
        "selected": concentration(K_sel, nq),
        "registered": concentration(K_reg, nq),
        "g_selected": g_sel, "g_registered": g_registered,
        "classical_kernel": crec["method"], "lambda": lam,
        "n_train": len(y_tr), "sqrt_n_ceiling": float(np.sqrt(len(y_tr))),
    }


def report(dataset, n_per_class, q_dir, c_dir, seeds):
    cell = PRIMARY_CELL[dataset]
    qpath = q_dir / f"{dataset}_matched_n{n_per_class}_bw.jsonl"
    cpath = c_dir / f"{dataset}_matched_n{n_per_class}.jsonl"
    if not qpath.exists() or not cpath.exists():
        print(f"\nmissing {qpath.name if not qpath.exists() else cpath.name}")
        return None

    qrecs = [json.loads(l) for l in qpath.open() if l.strip()]
    crecs = [json.loads(l) for l in cpath.open() if l.strip()]
    qs = {r["seed"]: [] for r in qrecs}
    for r in qrecs:
        if (r["mapping"], r["n_qubits"]) == cell:
            qs[r["seed"]].append(r)
    cs = {}
    for r in crecs:
        if (r["mapping"], r["n_qubits"]) == cell and r.get("track") == "matched":
            cs.setdefault(r["seed"], []).append(r)

    use = [s for s in sorted(set(qs) & set(cs)) if qs[s]][:seeds]
    print(f"\n{'=' * 74}")
    print(f"CLASSICAL LIMIT CHECK: {dataset}, {cell[0]}/{cell[1]} qubits, "
          f"{n_per_class} per class, {len(use)} seeds")
    print(f"{'=' * 74}")
    print("  Small-b limit of an angle fidelity kernel is RBF with gamma = (reps*b)^2/4.")
    print("  If the selected kernel IS that RBF, the bandwidth fix made it classical.\n")

    rows = [one_seed(dataset, cell, s, n_per_class,
                     best_by_inner(qs[s]), best_by_inner(cs[s])) for s in use]

    print("  gamma_pred and fit/pred apply to the ANGLE family only: (reps*b)^2/4 is")
    print("  the angle limit, and IQP repetitions carry entangling terms, so those")
    print("  cells are printed as '-'. rho is against each row's own best-fit RBF.\n")
    print(f"  {'seed':>4} {'set':<9} {'b':>7} {'C_cls':>8} {'g_pred':>9} {'g_fit':>9}"
          f" {'fit/pred':>9} {'rmse':>9} {'rho':>9} {'g_lam':>8}")
    for r in rows:
        ang_only = r["embedding"] == "angle"
        gp = f"{r['gamma_predicted']:.2e}" if ang_only else "-"
        ratio = f"{r['gamma_ratio']:.2f}" if ang_only else "-"
        ceiling = "!" if r["g_selected"] > r["sqrt_n_ceiling"] else " "
        print(f"  {r['seed']:>4} {r['setting']:<9} {r['bandwidth']:>7.4f} "
              f"{r['C_classical']:>8.0e} {gp:>9} {r['gamma_fitted']:>9.2e} "
              f"{ratio:>9} {r['rmse_best_fit_rbf']:>9.2e} "
              f"{r['spearman_offdiag_vs_best_fit']:>9.5f} "
              f"{r['g_selected']:>7.3f}{ceiling}")

    ang = [r for r in rows if r["embedding"] == "angle"]
    print(f"\n  Angle family ({len(ang)} of {len(rows)} seeds), where the analytic limit applies:")
    if ang:
        print(f"    max |K_quantum - K_RBF(predicted gamma)| : median "
              f"{np.median([r['max_abs_diff_vs_predicted_rbf'] for r in ang]):.2e}"
              f"   worst {max(r['max_abs_diff_vs_predicted_rbf'] for r in ang):.2e}")
        print(f"    Spearman of off-diagonals vs that RBF    : median "
              f"{np.median([r['spearman_offdiag_vs_predicted_rbf'] for r in ang]):.6f}"
              f"   worst {min(r['spearman_offdiag_vs_predicted_rbf'] for r in ang):.6f}")
        print(f"    fitted gamma / predicted gamma           : median "
              f"{np.median([r['gamma_ratio'] for r in ang]):.3f}")

    print(f"\n  Concentration of off-diagonal Gram entries:")
    for key, label in (("registered", "bandwidth 1.0 (registered)"),
                       ("selected", "bandwidth selected by inner CV")):
        m = np.median([r[key]["mean_offdiag"] for r in rows])
        s = np.median([r[key]["relative_spread"] for r in rows])
        floor = rows[0][key]["haar_floor"]
        print(f"    {label:<32} mean {m:.3e}   sd/mean {s:.3f}   "
              f"(2^-n floor = {floor:.3e})")

    ceil = rows[0]["sqrt_n_ceiling"]
    print(f"\n  Geometric difference, PREVIEW of week 5. sqrt(n) ceiling = {ceil:.2f};")
    print(f"  any g above it means lam is too small and the value says nothing about")
    print(f"  the kernels. lam from C = 1/(2*C*n), and C reached {max(r['C_classical'] for r in rows):.0e}.")
    br_s = sum(1 for r in rows if r["g_selected"] > ceil)
    br_r = sum(1 for r in rows if r["g_registered"] > ceil)
    print(f"    lam from C (as registered): median g {np.median([r['g_registered'] for r in rows]):.3f} "
          f"at bandwidth 1.0, {np.median([r['g_selected'] for r in rows]):.3f} at the selected "
          f"bandwidth")
    print(f"      ceiling breaches: {br_r}/{len(rows)} registered, {br_s}/{len(rows)} selected"
          f"{'   <- these values are not usable' if br_r or br_s else ''}")
    print(f"    {'lam':>10} {'g (bw 1.0)':>12} {'g (selected)':>14} {'breaches':>10}")
    for l in LAMBDA_SWEEP:
        k = f"{l:g}"
        gr = [r["g_lambda_sweep"][k]["registered"] for r in rows]
        gs = [r["g_lambda_sweep"][k]["selected"] for r in rows]
        br = sum(1 for v in gr + gs if v > ceil)
        print(f"    {l:>10.0e} {np.median(gr):>12.3f} {np.median(gs):>14.3f} {br:>10}")

    print(f"\n  READING, one line per embedding family, because they do NOT behave")
    print(f"  the same way and a single verdict across them would be wrong:")
    for fam in sorted({r["embedding"] for r in rows}):
        print(f"    * {_family_reading(rows, fam)}")
    return {"dataset": dataset, "n_per_class": n_per_class, "cell": list(cell),
            "seeds": use, "rows": rows,
            "bandwidths": dict(Counter(r["bandwidth"] for r in rows))}


def _family_reading(rows, family):
    sel = [r for r in rows if r["embedding"] == family]
    if not sel:
        return f"{family}: not selected by inner CV in any seed here."
    key = "spearman_offdiag_vs_best_fit"
    rho = float(np.median([r[key] for r in sel]))
    worst = float(min(r[key] for r in sel))
    diff = float(np.median([r["rmse_best_fit_rbf"] for r in sel]))
    n = f"{len(sel)}/{len(rows)} seeds"
    if rho > 0.9999 and worst > 0.999:
        return (f"{family} ({n}): IS the classical limit. Median Spearman {rho:.6f} "
                f"against its nearest RBF, worst {worst:.6f}, and both registered "
                f"endpoints are rank statistics. Any gain here is the kernel becoming "
                f"classical, and no advantage claim can rest on it.")
    if worst > 0.99:
        return (f"{family} ({n}): close to the classical limit but not inside it "
                f"(worst Spearman {worst:.5f}). Treat as classical for ranking "
                f"purposes and say so, but do not claim exact degeneracy.")
    return (f"{family} ({n}): NOT the classical limit. Worst Spearman {worst:.5f}, "
            f"median best-fit RMSE {diff:.2e}. This kernel stays genuinely distinct "
            f"from every RBF, so its performance is a property of the quantum kernel "
            f"and not of a classical kernel in disguise.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=sorted(PRIMARY_CELL))
    ap.add_argument("--n-per-class", type=int, default=250)
    ap.add_argument("--seeds", type=int, default=8,
                    help="seeds to reconstruct; each rebuilds Gram matrices from "
                         "scratch, so this is the cost knob")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--quantum-dir", default=str(ROOT / "results" / "runs" / "quantum"))
    ap.add_argument("--classical-dir", default=str(ROOT / "results" / "runs" / "classical"))
    ap.add_argument("--out", default=str(ROOT / "results" / "analysis" / "classical_limit.json"))
    args = ap.parse_args()

    if not args.all and not args.dataset:
        ap.error("give --dataset or --all")
    jobs = ([(d, args.n_per_class) for d in sorted(PRIMARY_CELL)] if args.all
            else [(args.dataset, args.n_per_class)])

    out = [r for r in (report(d, n, Path(args.quantum_dir), Path(args.classical_dir),
                              args.seeds) for d, n in jobs) if r]
    if out:
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"exploratory": True, "deviation": "D4",
                                 "results": out}, indent=2, default=float) + "\n")
        print(f"\n-> {p.relative_to(ROOT) if p.is_relative_to(ROOT) else p}")


if __name__ == "__main__":
    main()
