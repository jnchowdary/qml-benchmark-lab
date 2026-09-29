#!/usr/bin/env python3
"""Why does one seed breach the ceiling at lambda = 0.1? (D10 input)

WHY THIS EXISTS
---------------
The H2/H3 run returned NOT ESTABLISHED for both hypotheses because D5 requires
the conclusion to hold at every lambda where no unit breaches its sqrt(n)
ceiling, and no lambda column is breach-free. At lambda = 0.1 there are exactly
four breaching observations in 7,200, and all four are the same cell and seed --
churn, n=100, selectk, 4 qubits, seed 7 -- appearing once per quantum setting.
One seed of 1,800 voids the only column in which all 360 registered units
survive.

Before that is written into a deviation record, the mechanism matters. D5 says a
g above the ceiling means "the classical kernel is under-regularised in the g
computation". At lambda = 0.1 that explanation does not apply: lambda is not
small. So either D5's reading of the ceiling is incomplete, or something about
this particular classical kernel drives g up independently of lambda.

VERSION 1'S HYPOTHESIS, AND ITS REFUTATION BY ITS OWN OUTPUT
------------------------------------------------------------
Version 1 proposed that the selected classical kernel -- poly at C = 1e-04, the
bottom of the C grid -- was near rank-deficient, and that K_C's near-null space
drove g up independently of lambda. That is REFUTED. The lambda = 0.1
amplification max_i eig_i/(eig_i + lam)^2 measures 2.491 in the breaching cell
and 2.487 in a non-breaching cell at the same dataset, training size, qubit
count and seed. Identical to three decimals. The breaching cell has the LOWER
effective rank, 6 against 10, and the HIGHER participation ratio, 2.02 against
1.69, and neither matters because the quantity they feed is the same.

sqrt(2.491) is 1.58 against an observed g of 12.72, so the classical side
accounts for almost none of it. Since

    g^2 = ||sqrt(K_Q) sqrt(K_C) (K_C + lam I)^-2 sqrt(K_C) sqrt(K_Q)||_inf
       <= ||K_Q||_inf * max_i eig_i(K_C)/(eig_i(K_C) + lam)^2

the remaining factor must be ||K_Q||_inf, of order 65 for g^2 = 162. This
version therefore measures BOTH sides and the product bound, prints the actual
g beside it, and reports which factor separates the breaching cell from the
contrast -- or reports that neither does, if the bound turns out too loose to
be diagnostic. Choosing whichever story fits the numbers afterwards is the
error this whole project exists to document.

It computes nothing that feeds a hypothesis test. It reads two cells.

Usage:
    PYTHONPATH=src python scripts/diagnose_ceiling_breach.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from qbench.data import balanced_subsample, load_dataset, make_split  # noqa: E402
from qbench.features import fit_mapping, scale_to_angles  # noqa: E402
from qbench.kernels.classical import build_classical_kernel  # noqa: E402
from qbench.kernels.geometric_difference import (  # noqa: E402
    geometric_difference_regularised, normalise_kernel)
from qbench.kernels.quantum import QuantumGramFactory  # noqa: E402
from primary_tests import best_by_inner, load  # noqa: E402

# The breaching cell, taken from results/audits/g_units.jsonl, not chosen.
CELL = dict(dataset="churn", n_per_class=100, mapping="selectk", n_qubits=4, seed=7)
# A cell at the same training size that did NOT breach, as the contrast.
CONTROL = dict(dataset="churn", n_per_class=100, mapping="pca", n_qubits=4, seed=7)


SETTINGS = ("angle-r1", "angle-r2", "iqp-r1", "iqp-r2")


def amp(ev, lam):
    """max_i eig_i/(eig_i+lam)^2 -- the classical side of the g bound."""
    return float(np.max(ev / (ev + lam) ** 2)) if len(ev) else float("nan")


def quantum_side(Xa, nq, ceiling, Kc, label):
    """||K_Q|| for each setting, the product bound, and the ACTUAL g at 0.1."""
    Kc = np.asarray(Kc, dtype=float)
    ev_c = np.clip(np.linalg.eigvalsh(normalise_kernel(Kc)), 0.0, None)
    a = amp(ev_c, 1e-1)
    print(f"\n  QUANTUM SIDE ({label}); classical amplification at lam=0.1 is {a:.4f}")
    print(f"    {'setting':>9} {'||K_Q||':>10} {'eff rank':>9} {'bound g':>9} "
          f"{'actual g':>9} {'ceiling':>8} {'breach':>7}")
    fac = QuantumGramFactory(nq)
    for s_ in SETTINGS:
        Kq = np.asarray(fac.gram_fn({"embedding": s_.split("-")[0],
                                     "reps": int(s_[-1])})(Xa), dtype=float)
        ev_q = np.clip(np.linalg.eigvalsh(normalise_kernel(Kq)), 0.0, None)
        nq_norm = float(ev_q.max())
        eff = int((ev_q > 1e-6 * max(ev_q.max(), 1e-300)).sum())
        bound = float(np.sqrt(nq_norm * a))
        g = float(geometric_difference_regularised(Kc, Kq, lam=1e-1))
        print(f"    {s_:>9} {nq_norm:10.3f} {eff:>5}/{len(ev_q):<3} {bound:9.3f} "
              f"{g:9.3f} {ceiling:8.3f} {'YES' if g > ceiling else 'no':>7}")
    fac.clear()


def spectrum(K, label):
    Kn = normalise_kernel(np.asarray(K, dtype=float))
    ev = np.linalg.eigvalsh(Kn)
    ev = np.clip(ev, 0.0, None)
    n = len(ev)
    tol = 1e-6 * max(ev.max(), 1e-300)
    eff = int((ev > tol).sum())
    # Participation ratio: a scale-free count of "how many directions matter".
    pr = (ev.sum() ** 2) / max(float((ev ** 2).sum()), 1e-300)
    print(f"    {label}")
    print(f"      n={n}  eig max {ev.max():.4e}  min {ev.min():.4e}")
    print(f"      effective rank (eig > 1e-6 x max): {eff}/{n}"
          f"   participation ratio: {pr:.2f}")
    for lam in (1e-1, 1e-2, 1e-3):
        # The regularised inverse's amplification of the smallest retained mode.
        amp = float(np.max(ev / (ev + lam) ** 2)) if n else float("nan")
        print(f"      lam {lam:g}: max eig/(eig+lam)^2 = {amp:9.3f}"
              f"   -> g can reach sqrt of this times a K_Q factor")
    return ev


def one(cell, tag):
    print(f"\n{'=' * 74}\n{tag}: {cell}\n{'=' * 74}")
    crecs = [r for r in load(ROOT / "results" / "runs" / "classical"
                            / f"{cell['dataset']}_matched_n{cell['n_per_class']}.jsonl")
             if r["mapping"] == cell["mapping"]
             and int(r["n_qubits"]) == cell["n_qubits"]
             and int(r["seed"]) == cell["seed"]]
    print("  classical candidates, by inner score:")
    for r in sorted(crecs, key=lambda x: -float(x["inner_score"])):
        print(f"    {r['method']:>7}  C={float(r['C']):.0e}  "
              f"inner={float(r['inner_score']):.4f}  params={r.get('params')}")
    best = best_by_inner(crecs)
    print(f"  -> best_by_inner selects: {best['method']} at C={float(best['C']):.0e}")

    X, y, _ = load_dataset(cell["dataset"])
    Xs, ys = balanced_subsample(X, y, n_per_class=cell["n_per_class"],
                                seed=cell["seed"])
    X_tr, _, y_tr, _ = make_split(Xs, ys, seed=cell["seed"])
    Xm, _ = fit_mapping(X_tr, y_tr, cell["n_qubits"], cell["mapping"],
                        seed=cell["seed"])
    Xa, _ = scale_to_angles(Xm)
    Xa = np.asarray(Xa, dtype=float)
    print(f"\n  n_train = {Xa.shape[0]}, sqrt(n) ceiling = {np.sqrt(Xa.shape[0]):.4f}")

    print("\n  SELECTED classical kernel:")
    Kc = build_classical_kernel(best["method"], **(best.get("params") or {}))(Xa)
    spectrum(Kc, f"{best['method']} C={float(best['C']):.0e}")
    quantum_side(Xa, cell["n_qubits"], float(np.sqrt(Xa.shape[0])), Kc,
                 f"{tag}, against the selected {best['method']}")
    for m in ("linear", "rbf", "poly"):
        alt = [r for r in crecs if r["method"] == m]
        if not alt or m == best["method"]:
            continue
        a = sorted(alt, key=lambda x: -float(x["inner_score"]))[0]
        print(f"\n  not selected, for contrast:")
        spectrum(build_classical_kernel(m, **(a.get("params") or {}))(Xa),
                 f"{m} C={float(a['C']):.0e} inner={float(a['inner_score']):.4f}")


def main():
    print(__doc__.split("\n")[0])
    one(CELL, "THE BREACHING CELL")
    one(CONTROL, "A NON-BREACHING CELL, same dataset/size/qubits/seed")
    print(f"\n{'=' * 74}")
    print("READING")
    print(f"{'=' * 74}")
    print("  g^2 <= ||K_Q||_inf * max_i eig_i(K_C)/(eig_i(K_C)+lam)^2, so the two")
    print("  tables above separate the two factors. The classical amplification is")
    print("  2.491 in the breaching cell and 2.487 in the contrast: it cannot be")
    print("  what distinguishes them. Whatever does, appears in the ||K_Q|| column.")
    print()
    print("  Read the QUANTUM SIDE tables against each other. If ||K_Q|| is far")
    print("  larger in the breaching cell, then a ceiling breach at lam = 0.1 is a")
    print("  statement about the QUANTUM kernel's spectrum, and D5's description --")
    print("  'the classical kernel is under-regularised in the g computation' -- is")
    print("  not merely incomplete but names the wrong side. That matters for D10,")
    print("  because excluding a unit on this criterion would then be excluding it")
    print("  for a property of the very kernel whose advantage is under test, which")
    print("  is selection on the outcome rather than a regularisation safeguard.")
    print()
    print("  If instead ||K_Q|| is similar in both, neither factor explains it and")
    print("  the bound is too loose to be diagnostic; say so rather than choosing")
    print("  whichever story fits.")


if __name__ == "__main__":
    main()
