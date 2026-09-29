#!/usr/bin/env python3
"""Does quantum spectral concentration predict ceiling breaches? (D10 input)

THE CLAIM UNDER TEST, STATED BEFORE THE SAMPLE IS DRAWN
-------------------------------------------------------
One cell pair (scripts/diagnose_ceiling_breach.py) suggested a mechanism for why
g exceeds its sqrt(n) ceiling. The algebra:

    g^2 = ||sqrt(K_Q) A sqrt(K_Q)||_inf,  A = sqrt(K_C) (K_C + lam I)^-2 sqrt(K_C)

A's eigenvalues are mu/(mu+lam)^2 over K_C's spectrum, and that expression is
maximised at mu = lam where it equals 1/(4 lam). So the CLASSICAL side of g is
capped at 1/(4 lam) for any kernel whatsoever, and in both cells examined it sat
at that cap (2.491 and 2.487 against 1/(4x0.1) = 2.5) because both classical
Grams are rank-deficient and carry an eigenvalue near lam. Everything above the
cap therefore comes from K_Q, giving

    g <= sqrt(||K_Q||_inf / (4 lam))

and since the ceiling is sqrt(n), with K_Q normalised to trace n, a breach
requires

    ||K_Q||_inf / n  >  4 lam                                        (NECESSARY)

which is scale-free: the quantum Gram must hold more than 4*lam of its total
trace in a single eigenvalue. More than 40% at lam = 0.1, 4% at 1e-2, 0.4% at
1e-3, 0.04% at 1e-4.

This is a NECESSARY and not a sufficient condition, because the bound also needs
K_Q's leading eigenvector to align with the K_C mode nearest lam. The contrast
cell met the threshold (||K_Q|| = 72.7 against 56) and did not breach.

THE FALSIFIER, NAMED IN ADVANCE
-------------------------------
A necessary condition makes one sharp prediction: there must be ZERO cases where
g exceeds the ceiling while ||K_Q||/n <= 4 lam. One false negative refutes it.
That count is the headline of this script's output, per lambda, and it is what
decides whether D10 states a mechanism or records a single-cell observation.

Also reported: Spearman between concentration and g at each lambda, the
sufficiency gap (how often the threshold is met without a breach), and the
alignment factor that explains the gap.

HOW THE SAMPLE IS DRAWN, AND WHY IT IS NOT DRAWN ON THE OUTCOME
---------------------------------------------------------------
Stratified on DESIGN factors only -- dataset x training size x qubit count, 30
strata, two cells each -- with (mapping, seed) chosen by a fixed RNG seed. g is
never consulted in choosing what to sample. Selecting cells because they
breached, and then reporting that breaching cells are concentrated, would be the
circularity this project exists to document.

Four controls, each with a known answer, run before anything is sampled. The
fourth is the important one: this script recomputes g from scratch and must
reproduce the value already in g_units.jsonl. If it cannot, it is measuring a
different quantity than the test did and nothing below it means anything.

Usage:
    PYTHONPATH=src python scripts/sample_ceiling_mechanism.py
    PYTHONPATH=src python scripts/sample_ceiling_mechanism.py --per-stratum 3 \
        --json results/audits/ceiling_mechanism.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from qbench.data import balanced_subsample, load_dataset, make_split  # noqa: E402
from qbench.stats import fmt_rho, rank_correlation  # noqa: E402
from qbench.features import fit_mapping, scale_to_angles  # noqa: E402
from qbench.kernels.classical import build_classical_kernel  # noqa: E402
from qbench.kernels.geometric_difference import (  # noqa: E402
    _matrix_sqrt_psd, _spectral_norm_sym, normalise_kernel)
from qbench.kernels.quantum import QuantumGramFactory  # noqa: E402
from primary_tests import best_by_inner, load  # noqa: E402

LAMBDAS = (1e-1, 1e-2, 1e-3, 1e-4)
SETTINGS = ("angle-r1", "angle-r2", "iqp-r1", "iqp-r2")
MAPPINGS = ("pca", "selectk", "randproj")
QUBITS = (4, 6, 8, 10, 12)
SIZES = (250, 100, 50)
DATASETS = ("churn", "fraud")
SAMPLE_SEED = 20260929          # fixed, declared, never tuned


# ------------------------------------------------------------------ the maths

def decompose(Kc_raw, Kq_raw, lam):
    """Split g into its classical cap, its quantum factor and their alignment."""
    Kc = normalise_kernel(np.asarray(Kc_raw, dtype=float))
    Kq = normalise_kernel(np.asarray(Kq_raw, dtype=float))
    n = Kc.shape[0]

    ev_q, V_q = np.linalg.eigh(Kq)
    ev_q = np.clip(ev_q, 0.0, None)
    top = float(ev_q[-1])
    v = V_q[:, -1]
    tol = 1e-6 * max(top, 1e-300)

    sq_c = _matrix_sqrt_psd(Kc)
    inner = np.linalg.solve(Kc + lam * np.eye(n), sq_c)
    A = inner @ inner.T
    a_max = float(_spectral_norm_sym(A))
    a_q = float(v @ A @ v)

    sq_q = _matrix_sqrt_psd(Kq)
    g = float(np.sqrt(max(_spectral_norm_sym(sq_q @ A @ sq_q), 0.0)))

    return {
        "lam": lam, "n": n, "g": g,
        "kq_norm": top, "kq_conc": top / n,
        "kq_eff_rank": int((ev_q > tol).sum()),
        "classical_amp": a_max, "classical_cap": 1.0 / (4.0 * lam),
        "amp_at_cap": a_max / (1.0 / (4.0 * lam)),
        "align": (a_q / a_max) if a_max > 0 else float("nan"),
        "bound": float(np.sqrt(top * a_max)),
        "threshold": 4.0 * lam,
        "predicts_breach": bool(top / n > 4.0 * lam),
        "breaches": bool(g > np.sqrt(n)),
    }


# ------------------------------------------------------------------ controls

def controls(rows_for_D):
    ok = {}
    n = 60
    ones = np.ones((n, n))
    d = decompose(np.eye(n) + 0.5 * ones, ones, 1e-1)
    ok["J rank-1 Gram -> conc 1.0, eff rank 1"] = (
        abs(d["kq_conc"] - 1.0) < 1e-9 and d["kq_eff_rank"] == 1,
        f"conc {d['kq_conc']:.6f}, eff rank {d['kq_eff_rank']}")

    d = decompose(np.eye(n) + 0.5 * ones, np.eye(n), 1e-1)
    ok["K identity Gram -> conc 1/n, eff rank n"] = (
        abs(d["kq_conc"] - 1.0 / n) < 1e-9 and d["kq_eff_rank"] == n,
        f"conc {d['kq_conc']:.6f} vs 1/n {1/n:.6f}, eff rank {d['kq_eff_rank']}")

    # The classical factor can never exceed 1/(4 lam). Probe kernels that should
    # sit at the cap and one that cannot reach it.
    rng = np.random.default_rng(0)
    X = rng.normal(size=(n, 4))
    sq = np.sum((X[:, None, :] - X[None, :, :]) ** 2, axis=-1)
    caps = []
    for lam in LAMBDAS:
        d = decompose(np.exp(-0.3 * sq), np.exp(-0.9 * sq), lam)
        caps.append(d["classical_amp"] <= d["classical_cap"] * (1 + 1e-9))
    ok["L classical factor <= 1/(4 lam) always"] = (
        all(caps), f"cap respected at all {len(LAMBDAS)} lambdas")

    # The one that matters: reproduce the sweep's own g. Relative, because g
    # reaches ~50 here and an absolute 1e-8 would fail on float reordering alone.
    # decompose() builds A exactly as g_for_settings does, so agreement should be
    # at machine precision; a real disagreement means this script is measuring a
    # different quantity than the test did.
    worst_abs, worst_rel, checked = 0.0, 0.0, 0
    for stored, recomputed in rows_for_D:
        d = abs(stored - recomputed)
        worst_abs = max(worst_abs, d)
        worst_rel = max(worst_rel, d / max(abs(stored), 1.0))
        checked += 1
    ok["M reproduces g_units.jsonl"] = (
        checked > 0 and worst_rel < 1e-9,
        f"{checked} observations, max |diff| {worst_abs:.2e}, "
        f"max relative {worst_rel:.2e}"
        if checked else "NOT CHECKED -- no rows compared")
    for k, (passed, detail) in ok.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {k:<42} {detail}")
    return all(p for p, _ in ok.values())


# ------------------------------------------------------------------ sampling

def draw(per_stratum):
    """Stratified on design factors only. g is never consulted."""
    rng = np.random.default_rng(SAMPLE_SEED)
    picks = []
    for ds in DATASETS:
        for npc in SIZES:
            for nq in QUBITS:
                for _ in range(per_stratum):
                    picks.append((ds, npc,
                                  MAPPINGS[int(rng.integers(len(MAPPINGS)))],
                                  nq, int(rng.integers(20))))
    seen, out = set(), []
    for p in picks:                      # de-duplicate, keep order
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def measure(cell, stored):
    ds, npc, mapping, nq, seed = cell
    crecs = [r for r in load(ROOT / "results" / "runs" / "classical"
                             / f"{ds}_matched_n{npc}.jsonl")
             if r["mapping"] == mapping and int(r["n_qubits"]) == nq
             and int(r["seed"]) == seed]
    if not crecs:
        return []
    best = best_by_inner(crecs)

    X, y, _ = load_dataset(ds)
    Xs, ys = balanced_subsample(X, y, n_per_class=npc, seed=seed)
    X_tr, _, y_tr, _ = make_split(Xs, ys, seed=seed)
    Xm, _ = fit_mapping(X_tr, y_tr, nq, mapping, seed=seed)
    Xa, _ = scale_to_angles(Xm)
    Xa = np.asarray(Xa, dtype=float)
    Kc = build_classical_kernel(best["method"], **(best.get("params") or {}))(Xa)

    fac = QuantumGramFactory(nq)
    out = []
    for s in SETTINGS:
        key = (ds, npc, mapping, nq, s, seed)
        Kq = fac.gram_fn({"embedding": s.split("-")[0], "reps": int(s[-1])})(Xa)
        for lam in LAMBDAS:
            d = decompose(Kc, Kq, lam)
            d.update(dataset=ds, n_per_class=npc, mapping=mapping, n_qubits=nq,
                     setting=s, seed=seed, classical_method=best["method"],
                     classical_C=float(best["C"]),
                     stored_g=stored.get((key, f"{lam:g}")))
            out.append(d)
    fac.clear()
    return out


# -------------------------------------------------------------------- report

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--per-stratum", type=int, default=2,
                    help="cells per (dataset, size, qubits) stratum; 30 strata")
    ap.add_argument("--units", default="results/audits/g_units.jsonl")
    ap.add_argument("--json", help="write the full measurement table here")
    args = ap.parse_args()

    print(__doc__.split("\n")[0])
    print(f"\nSample: stratified on design factors only, seed {SAMPLE_SEED}, "
          f"{args.per_stratum} per stratum.")

    stored = {}
    for line in Path(args.units).read_text().splitlines():
        if not line:
            continue
        r = json.loads(line)
        key = (r["dataset"], r["n_per_class"], r["mapping"], r["n_qubits"],
               r["setting"], r["seed"])
        for k, v in r["g"].items():
            stored[(key, k)] = float(v)

    cells = draw(args.per_stratum)
    print(f"  {len(cells)} distinct cells after de-duplication, "
          f"{len(cells) * len(SETTINGS) * len(LAMBDAS)} observations to compute.\n")

    rows = []
    for i, cell in enumerate(cells, 1):
        rows.extend(measure(cell, stored))
        if i % 10 == 0:
            print(f"  {i}/{len(cells)} cells")

    print("\nControls:")
    pairs = [(r["stored_g"], r["g"]) for r in rows if r["stored_g"] is not None]
    if not controls(pairs):
        raise SystemExit("\n  A control failed. Nothing below it is interpretable.")

    print(f"\n{'=' * 78}\nTHE FALSIFIER: breaches with concentration AT OR BELOW "
          f"the 4*lam threshold\n{'=' * 78}")
    print(f"  {'lam':>7} {'obs':>5} {'breach':>7} {'predicted':>10} "
          f"{'FALSE NEG':>10} {'met, no breach':>15} {'sensitivity':>12}")
    report = {"sample_seed": SAMPLE_SEED, "per_stratum": args.per_stratum,
              "n_cells": len(cells), "by_lambda": {}}
    verdicts = []
    for lam in LAMBDAS:
        sub = [r for r in rows if r["lam"] == lam]
        br = [r for r in sub if r["breaches"]]
        pred = [r for r in sub if r["predicts_breach"]]
        fneg = [r for r in br if not r["predicts_breach"]]
        met_no = [r for r in pred if not r["breaches"]]
        sens = (1 - len(fneg) / len(br)) if br else float("nan")
        print(f"  {lam:>7.0e} {len(sub):5d} {len(br):7d} {len(pred):10d} "
              f"{len(fneg):10d} {len(met_no):15d} "
              f"{('n/a' if not br else f'{sens:.4f}'):>12}")
        report["by_lambda"][f"{lam:g}"] = {
            "n": len(sub), "breaches": len(br), "predicted": len(pred),
            "false_negatives": len(fneg), "met_no_breach": len(met_no),
            "sensitivity": None if not br else sens,
            "false_negative_examples": [
                {k: r[k] for k in ("dataset", "n_per_class", "mapping",
                                   "n_qubits", "setting", "seed", "g",
                                   "kq_conc", "threshold")} for r in fneg[:5]]}
        verdicts.append(len(fneg) == 0)
        for r in fneg[:3]:
            print(f"           REFUTING CASE: {r['dataset']} n={r['n_per_class']} "
                  f"{r['mapping']} {r['n_qubits']}q {r['setting']} seed {r['seed']}: "
                  f"g={r['g']:.3f} > sqrt(n)={np.sqrt(r['n']):.3f} but "
                  f"conc={r['kq_conc']:.5f} <= {r['threshold']:.4f}")

    print(f"\n  NECESSARY CONDITION: "
          f"{'HOLDS at every lambda' if all(verdicts) else 'REFUTED'}"
          f" ({sum(verdicts)}/{len(verdicts)} lambdas with zero false negatives)")

    print(f"\n{'=' * 78}\nIS THE CLASSICAL SIDE PINNED AT ITS CAP, AS THE ONE-CELL "
          f"PAIR SUGGESTED?\n{'=' * 78}")
    print(f"  {'lam':>7} {'cap 1/(4lam)':>13} {'median amp/cap':>15} "
          f"{'min':>8} {'frac > 0.99':>12}")
    for lam in LAMBDAS:
        v = np.array([r["amp_at_cap"] for r in rows if r["lam"] == lam])
        print(f"  {lam:>7.0e} {1/(4*lam):13.3f} {np.median(v):15.4f} "
              f"{v.min():8.4f} {float((v > 0.99).mean()):12.3f}")
        report["by_lambda"][f"{lam:g}"]["median_amp_at_cap"] = float(np.median(v))

    print(f"\n{'=' * 78}\nDOES CONCENTRATION TRACK g, AND DOES ALIGNMENT EXPLAIN "
          f"THE SUFFICIENCY GAP?\n{'=' * 78}")
    print(f"  {'lam':>7} {'rho(conc, g)':>13} {'p':>10} "
          f"{'rho(rank, g)':>13} {'align: breach':>14} {'align: not':>11}")
    for lam in LAMBDAS:
        sub = [r for r in rows if r["lam"] == lam]
        c = [r["kq_conc"] for r in sub]
        g = [r["g"] for r in sub]
        rk = [r["kq_eff_rank"] for r in sub]
        rc1 = rank_correlation(c, g)
        rc2 = rank_correlation(rk, g)
        ab = [r["align"] for r in sub if r["breaches"]]
        an = [r["align"] for r in sub if not r["breaches"]]
        print(f"  {lam:>7.0e} {fmt_rho(rc1, 13)} "
              f"{(f'{rc1.p:.2e}' if rc1.ok else 'n/a'):>10} {fmt_rho(rc2, 13)} "
              f"{(f'{np.median(ab):.4f}' if ab else 'n/a'):>14} "
              f"{(f'{np.median(an):.4f}' if an else 'n/a'):>11}")
        report["by_lambda"][f"{lam:g}"].update(
            rho_conc_g=float(rho), p_conc_g=float(p),
            rho_rank_g=float(rho2),
            median_align_breach=None if not ab else float(np.median(ab)),
            median_align_nonbreach=None if not an else float(np.median(an)))

    viol = [r for r in rows if r["g"] > r["bound"] * (1 + 1e-6)]
    print(f"\n  Bound g <= sqrt(||K_Q|| * classical_amp) violated in "
          f"{len(viol)}/{len(rows)} observations."
          + ("" if not viol else "  <- the algebra above is WRONG, not the data"))
    report["bound_violations"] = len(viol)

    if args.json:
        p = Path(args.json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({**report, "rows": rows}, indent=2,
                                default=float) + "\n")
        print(f"\n-> {p}")


if __name__ == "__main__":
    main()
