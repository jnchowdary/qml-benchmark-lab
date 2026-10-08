#!/usr/bin/env python3
"""D16: Huang's own lambda selection, g_tra over his declared grid.

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------
`docs/deviations.md` D16 specifies this analysis in full and was committed and
pushed before this script existed. Read it first; this file implements it and
decides nothing.

It is a **prospectively specified follow-up analysis**. It is not part of the
registered confirmatory design and cannot become part of it. No outcome here may
be reported as a confirmatory result.

THE RULE (D16 section 1)
------------------------
Report g_gen at the LARGEST lambda in Huang's declared grid satisfying
`g_tra <= 0.045`. The source is internally inconsistent on that boundary,
writing `<=` in one place and `<` in the numerical-details passage. D16 selects
`<=` and publishes the count of rows within 1e-9 of 0.045 instead of resolving
the ambiguity silently.

THE OUTCOME IS ALREADY DETERMINED (D16 section 10)
--------------------------------------------------
g_gen is non-increasing in lambda and the grid's maximum is 0.1, so every
selected lambda is at most 0.1 and `g_gen(lambda*) >= g_gen(0.1)` for every row.
The ceiling does not depend on lambda. **Every row that breaches at lambda = 0.1
breaches under this rule**, and the lambda = 0.1 column has four breaching rows.
So the column cannot be breach-free: outcome B1 is excluded in advance and the
result is B2 or B3. **If this run returns a breach-free column, the
implementation is wrong rather than the proof**, and D16 pre-commits that case
as an invalid run.

What the run is still for: the lambda values Huang's own rule selects on this
data, g at those lambda, and whether his rule is satisfiable here at all. That
is the quantity neither this project nor Florez Ablan et al. computed.

THE GRID IS A SUPERSET OF THE FROZEN SWEEP
------------------------------------------
Huang's {1e-5, 1e-4, 1e-3, 1e-2, 0.025, 0.05, 0.1} contains all four frozen
lambdas, so this run recomputes the frozen columns for free and the integrity
gate in `scripts/check_gtra_run.py` compares them bit-identically against
`results/audits/g_units.jsonl`. Grams come from `geometric_tests.build_pair`,
the only place in the project that builds them, so this sweep cannot drift from
the confirmatory one in how the matrices are constructed.

Usage:
    PYTHONPATH=src python scripts/gtra_sweep.py --controls-only
    PYTHONPATH=src python scripts/gtra_sweep.py --limit 2 --out /tmp/gtra_smoke.jsonl
    PYTHONPATH=src python scripts/gtra_sweep.py
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from qbench.kernels.geometric_difference import (  # noqa: E402
    _matrix_sqrt_psd, _spectral_norm_sym, geometric_difference_regularised,
    geometric_difference_training, normalise_kernel)
from geometric_tests import (  # noqa: E402
    LAMBDAS, MAPPINGS, QUBITS, SETTINGS, SIZES, build_pair, index)
from primary_tests import load, norm_ap  # noqa: E402

# D16 section 1. Frozen exactly, and Huang's rather than this project's.
HUANG_GRID = (1e-5, 1e-4, 1e-3, 1e-2, 0.025, 0.05, 0.1)
GTRA_MAX = 0.045                 # the threshold; `<=` per D16, not `<`
NEAR_BOUNDARY = 1e-9             # only rows this close could differ under `<`

# D16 section 8. The bandwidth arm bears on no hypothesis and is excluded.
ARM = "registered"


def g_pair_over_grid(K_c, K_qs, lams):
    """g_gen AND g_tra for several quantum kernels against ONE classical kernel.

    g_gen's classical core is hoisted out of the per-setting loop exactly as
    `geometric_tests.g_for_settings` hoists it, because K_C does not change
    across the four settings in a cell:

        g_gen = sqrt( || sqrt(K_Q) [ sqrt(K_C) (K_C+lam I)^-2 sqrt(K_C) ] sqrt(K_Q) || )

    g_tra IS DELIBERATELY NOT HOISTED THE SAME WAY, and this cost one iteration
    to learn. The module computes

        A = solve(K_C + lam I, sqrt(K_Q));   g_tra = lam * sqrt(|| A^T A ||)

    which cannot be factored out of the setting loop, because A depends on K_Q.
    The first version of this function solved for the full inverse instead,
        inv = solve(K_C + lam I, I);  core = inv @ inv^T
    and sandwiched it, which is the same quantity in exact arithmetic and
    **differs from the module by one ulp in floating point**: control B read
    2.22e-16 rather than zero. A tolerance would have made it pass and would have
    left the sweep computing g_tra by arithmetic no test in this project covers.
    So the operation order matches the module exactly and only the K_Q square
    root and the normalisations are hoisted, which control A already proves is
    bit-exact. The price is 28 triangular solves per cell instead of 7, against
    four quantum Grams per cell: nothing.

    Controls A and B prove both paths equal the module functions rather than
    assuming it, which is the only reason any hoisted copy is allowed to exist.
    """
    K_c = normalise_kernel(np.asarray(K_c, dtype=float))
    n = K_c.shape[0]
    eye = np.eye(n)
    sqrt_Kc = _matrix_sqrt_psd(K_c)

    core_gen = {}
    for lam in lams:
        inner = np.linalg.solve(K_c + lam * eye, sqrt_Kc)
        core_gen[lam] = inner @ inner.T

    gen, tra = {}, {}
    for name, K_q in K_qs.items():
        sq = _matrix_sqrt_psd(normalise_kernel(np.asarray(K_q, dtype=float)))
        gen[name] = {lam: float(np.sqrt(max(
            _spectral_norm_sym(sq @ core_gen[lam] @ sq), 0.0))) for lam in lams}
        t = {}
        for lam in lams:
            A = np.linalg.solve(K_c + lam * eye, sq)
            t[lam] = float(lam * np.sqrt(max(_spectral_norm_sym(A.T @ A), 0.0)))
        tra[name] = t
    return gen, tra, float(np.sqrt(n))


def select_lambda(gtra_by_lam):
    """D16 sections 1 and 5: the largest grid lambda with g_tra <= 0.045.

    Monotonicity makes this well posed (g_tra is non-decreasing in lambda, so the
    admissible set is a down-set), but the maximum is taken over the admissible
    set directly rather than by trusting monotonicity, so a violation shows up as
    a selection the gate can catch rather than as a silently wrong answer.
    """
    admissible = [l for l in HUANG_GRID if gtra_by_lam[l] <= GTRA_MAX]
    near = sum(1 for l in HUANG_GRID
               if abs(gtra_by_lam[l] - GTRA_MAX) < NEAR_BOUNDARY)
    if not admissible:
        return None, False, near
    return max(admissible), True, near


def controls(verbose=True):
    """Prove the hoisted arithmetic equals the module's, before any sweep."""
    rng = np.random.default_rng(7)
    A = rng.normal(size=(14, 14))
    B = rng.normal(size=(14, 10))
    K_c = A @ A.T + 1e-3 * np.eye(14)
    K_q = B @ B.T + 1e-3 * np.eye(14)
    gen, tra, ceiling = g_pair_over_grid(K_c, {"q": K_q}, HUANG_GRID)

    ok = {}
    worst = max(abs(gen["q"][l] - geometric_difference_regularised(
        K_c, K_q, lam=l, warn_above_ceiling=False)) for l in HUANG_GRID)
    ok["A g_gen fast path == module"] = (worst == 0.0, f"max |diff| {worst:.2e}")

    worst = max(abs(tra["q"][l] - geometric_difference_training(K_c, K_q, lam=l))
                for l in HUANG_GRID)
    ok["B g_tra fast path == module"] = (worst == 0.0, f"max |diff| {worst:.2e}")

    ok["C grid contains the frozen sweep"] = (
        set(LAMBDAS) <= set(HUANG_GRID),
        f"frozen {sorted(LAMBDAS)} inside {list(HUANG_GRID)}")

    vals = [tra["q"][l] for l in HUANG_GRID]
    ok["D g_tra non-decreasing in lam"] = (
        all(b >= a for a, b in zip(vals, vals[1:])),
        f"{vals[0]:.3e} -> {vals[-1]:.3e} across {len(HUANG_GRID)} lambdas")

    vals = [gen["q"][l] for l in HUANG_GRID]
    ok["E g_gen non-increasing in lam"] = (
        all(b <= a for a, b in zip(vals, vals[1:])),
        f"{vals[0]:.3e} -> {vals[-1]:.3e}; the proof in D16 section 10 rests on this")

    # F: selection returns the largest admissible lambda, and None when the rule
    # cannot be met. Built from a dict rather than a kernel so the boundary is
    # exact rather than whatever a random matrix happens to give.
    easy = {l: 0.001 for l in HUANG_GRID}
    hard = {l: 0.9 for l in HUANG_GRID}
    mixed = {l: (0.001 if l <= 1e-2 else 0.9) for l in HUANG_GRID}
    at_bound = {**mixed, 1e-2: GTRA_MAX}
    sel_easy, _, _ = select_lambda(easy)
    sel_hard, adm_hard, _ = select_lambda(hard)
    sel_mixed, _, _ = select_lambda(mixed)
    sel_bound, _, near_bound = select_lambda(at_bound)
    ok["F selection takes the largest admissible"] = (
        sel_easy == 0.1 and sel_hard is None and adm_hard is False
        and sel_mixed == 1e-2 and sel_bound == 1e-2 and near_bound == 1,
        f"all-ok -> {sel_easy}, none-ok -> {sel_hard}, mixed -> {sel_mixed}, "
        f"exactly-at-0.045 -> {sel_bound} (admitted under '<=', near count {near_bound})")

    if verbose:
        print(f"\nControls on the D16 grid (no row is written here):")
        for k, (passed, detail) in ok.items():
            print(f"  [{'PASS' if passed else 'FAIL'}] {k:<36} {detail}")
    return all(p for p, _ in ok.values())


def cell_rows(dataset, n_per_class, mapping, nq, seed, q_by, c_by):
    """One row per setting for one (cell, seed), or None if records are short."""
    pair = build_pair(dataset, n_per_class, mapping, nq, seed, q_by, c_by)
    if pair is None:
        return None
    Xa, K_c, K_qs, best_c, qrecs = pair
    gen, tra, ceiling = g_pair_over_grid(K_c, K_qs, HUANG_GRID)
    c_nap = norm_ap(best_c)

    rows = []
    for s in SETTINGS:
        g_by, t_by = gen[s], tra[s]
        sel, admissible, near = select_lambda(t_by)
        finite = all(np.isfinite(v) for v in list(g_by.values()) + list(t_by.values()))
        tvals = [t_by[l] for l in HUANG_GRID]
        bigger = [l for l in HUANG_GRID if sel is not None and l > sel]
        rows.append({
            "arm": ARM, "dataset": dataset, "n_per_class": n_per_class,
            "mapping": mapping, "n_qubits": nq, "setting": s, "seed": seed,
            "quantum_params": dict(qrecs[s]["params"]),
            "quantum_bandwidth": float(qrecs[s]["params"].get("bandwidth", 1.0)),
            "classical_method": best_c["method"], "classical_C": float(best_c["C"]),
            "ceiling": ceiling,
            "g": {f"{l:g}": g_by[l] for l in HUANG_GRID},
            "g_tra": {f"{l:g}": t_by[l] for l in HUANG_GRID},
            # D16 section 7: no fallback lambda is ever substituted.
            "selected_lambda": sel,
            "admissible": bool(admissible),
            "valid": bool(finite),
            "g_selected": (g_by[sel] if sel is not None else None),
            "g_tra_selected": (t_by[sel] if sel is not None else None),
            "gtra_margin": ((GTRA_MAX - t_by[sel]) if sel is not None else None),
            "next_larger_lambda": (min(bigger) if bigger else None),
            "g_tra_next_larger": (t_by[min(bigger)] if bigger else None),
            "near_boundary_count": near,
            "gtra_monotone": all(b >= a for a, b in zip(tvals, tvals[1:])),
            "breach": (bool(g_by[sel] > ceiling) if sel is not None else None),
            "d_normap": norm_ap(qrecs[s]) - c_nap,
        })
    return rows


def sweep(datasets, sizes, out_path, q_dir, c_dir, limit=None,
          mappings=MAPPINGS, qubits=QUBITS):
    done = set()
    p = Path(out_path)
    if p.exists():
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("arm", ARM) != ARM:
                raise SystemExit(
                    f"\n  {p} holds arm '{r.get('arm')}' and D16 section 8 "
                    f"specifies '{ARM}' only. Write elsewhere.")
            done.add((r["dataset"], r["n_per_class"], r["mapping"],
                      r["n_qubits"], r["seed"]))
        print(f"  resuming: {len(done)} (cell, seed) combinations already done")
    p.parent.mkdir(parents=True, exist_ok=True)
    t0, n = time.perf_counter(), 0
    with p.open("a") as fh:
        for dataset, npc in itertools.product(datasets, sizes):
            qf = Path(q_dir) / f"{dataset}_matched_n{npc}.jsonl"
            cf = Path(c_dir) / f"{dataset}_matched_n{npc}.jsonl"
            q, c = load(qf), load(cf)
            if not q or not c:
                missing = [f.name for f, v in ((qf, q), (cf, c)) if not v]
                print(f"  skipping {dataset} n={npc}: missing or empty "
                      f"{', '.join(missing)}")
                continue
            q_by, c_by = index(q), index(c)
            seeds = sorted({int(r["seed"]) for r in q})
            for mapping, nq, seed in itertools.product(mappings, qubits, seeds):
                if (dataset, npc, mapping, nq, seed) in done:
                    continue
                rows = cell_rows(dataset, npc, mapping, nq, seed, q_by, c_by)
                if rows is None:
                    continue
                for r in rows:
                    fh.write(json.dumps(r, default=float) + "\n")
                fh.flush()
                n += 1
                if limit and n >= limit:
                    dt = (time.perf_counter() - t0) / 60
                    print(f"  stopped at --limit {limit}: {n} cells in "
                          f"{dt * 60:.1f} s")
                    return
                if n % 25 == 0:
                    dt = (time.perf_counter() - t0) / 60
                    print(f"  {n} cells, {dt:.1f} min, {dt * 60 / n:.1f} s/cell")
    dt = (time.perf_counter() - t0) / 60
    print(f"  {n} new (cell, seed) combinations in {dt:.1f} min")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--controls-only", action="store_true")
    ap.add_argument("--out", default="results/audits/g_units_gtra.jsonl")
    ap.add_argument("--limit", type=int, help="stop after N cells (smoke test)")
    ap.add_argument("--datasets", nargs="*", default=["churn", "fraud"])
    ap.add_argument("--sizes", nargs="*", type=int, default=list(SIZES))
    ap.add_argument("--quantum-dir", default=str(ROOT / "results" / "runs" / "quantum"))
    ap.add_argument("--classical-dir", default=str(ROOT / "results" / "runs" / "classical"))
    args = ap.parse_args()

    print("\nD16: Huang's g_tra selection over his declared grid.")
    print(f"Grid {list(HUANG_GRID)}, threshold g_tra <= {GTRA_MAX}, arm '{ARM}'.")
    print("A prospectively specified FOLLOW-UP analysis. Not confirmatory, and")
    print("it cannot become confirmatory. D16 section 10 excludes a breach-free")
    print("column in advance: if one appears, the implementation is wrong.")

    if not controls():
        raise SystemExit("\n  Controls failed. No sweep was run.\n")
    if args.controls_only:
        print("\n  Controls only. Nothing written.\n")
        return

    sweep(args.datasets, args.sizes, args.out, Path(args.quantum_dir),
          Path(args.classical_dir), args.limit)
    print(f"\n-> {args.out}")
    print("  Now run scripts/check_gtra_run.py. The gate comes before the result.\n")


if __name__ == "__main__":
    main()
