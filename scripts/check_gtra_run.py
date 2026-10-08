#!/usr/bin/env python3
"""The integrity gate for D16's g_tra run. Section 9 of the pre-commitment.

WHY THIS EXISTS
---------------
`scripts/gtra_sweep.py` computes g_gen and g_tra over Huang's declared grid and
selects lambda by his own rule. Huang's grid CONTAINS all four frozen lambdas, so
the run recomputes the frozen columns for free and they must come back
bit-identical. If any of them moved, the run is invalid: nothing is read from it
and the difference is a defect to investigate rather than a result.

Beyond that, this gate checks the things the proof in D16 section 10 cannot:
that the stored selection really is the maximum of the stored admissible set,
that a row selecting lambda = 0.1 reproduces the frozen lambda = 0.1 value
exactly, and that both monotonicity directions hold on the real data rather than
only on a constructed pair.

The gate prints NO selected-lambda value, NO breach count and NO outcome.
Reading those is a separate step behind --branch, which refuses to run unless the
gate has passed in the same invocation.

Usage:
    python scripts/check_gtra_run.py
    python scripts/check_gtra_run.py --branch     # gate, then the outcome
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

HUANG_GRID = (1e-5, 1e-4, 1e-3, 1e-2, 0.025, 0.05, 0.1)
GTRA_MAX = 0.045
NEAR_BOUNDARY = 1e-9

# D16 amendment, 8 October 2026, declared and pushed before the outcome was read.
# g_tra's monotonicity in lambda is a theorem in exact arithmetic and the first
# version of this gate compared strictly. It failed on 64 (row, lambda-pair)
# instances of 7,200 rows at a worst relative size of 4.693e-11, which is what a
# solve against a Gram matrix of condition 1e+19 to 1e+33 accumulates. Three
# quarters sit at the 1e-5 -> 1e-4 step, where K_C + lam*I is nearest singular.
#
# Two clauses replace the one. MONO_REL_TOL is loose, on the cosmetic property,
# at roughly 200x the measured worst case. MONO_THRESH_GUARD is tight, on the
# property that decides anything: a violation matters only if a value involved
# sits near 0.045, because that is the only way rounding could move an
# admissibility decision. The nearest currently comes to within 0.9848.
MONO_REL_TOL = 1e-8        # fails the run above this relative decrease
MONO_THRESH_GUARD = 1e-6   # fails the run if a violating value is this near 0.045

# The frozen sweep, which Huang's grid contains. These must not move.
FROZEN = ("0.1", "0.01", "0.001", "0.0001")

# Fields that cannot depend on lambda, so any movement is a defect.
INVARIANT = ("d_normap", "ceiling", "classical_C", "classical_method",
             "quantum_bandwidth", "n_qubits", "arm")

KEY = ("arm", "dataset", "n_per_class", "mapping", "n_qubits", "setting", "seed")


def key_of(r):
    return tuple(r.get(f) for f in KEY)


def load(path):
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"\n  {p} does not exist.\n")
    out = {}
    for i, line in enumerate(p.open(), 1):
        if not line.strip():
            continue
        r = json.loads(line)
        k = key_of(r)
        if k in out:
            raise SystemExit(f"\n  {p} line {i}: duplicate key {k}\n")
        out[k] = r
    return out


def gate(old, new, verbose=True):
    """True only if the run is valid. Every failure class is printed."""
    fails = []
    gk = lambda l: f"{l:g}"  # noqa: E731  -- the key format gtra_sweep writes

    if len(new) != len(old):
        fails.append(f"row count: {len(new)} new against {len(old)} old")
    missing = sorted(set(old) - set(new))
    extra = sorted(set(new) - set(old))
    if missing:
        fails.append(f"{len(missing)} keys absent from the run, first {missing[0]}")
    if extra:
        fails.append(f"{len(extra)} keys only in the run, first {extra[0]}")
    shared = sorted(set(old) & set(new))

    # 1. The frozen columns, bit-identical.
    frozen_bad = {c: [] for c in FROZEN}
    for k in shared:
        go, gn = old[k].get("g", {}), new[k].get("g", {})
        for c in FROZEN:
            if c not in go or c not in gn:
                frozen_bad[c].append((k, "column absent"))
            elif go[c] != gn[c]:
                frozen_bad[c].append((k, f"{go[c]!r} -> {gn[c]!r}"))
    for c, bad in frozen_bad.items():
        if bad:
            fails.append(f"frozen column {c}: {len(bad)} rows differ, "
                         f"first {bad[0][0]} {bad[0][1]}")

    # 2. Lambda-independent fields.
    for f in INVARIANT:
        bad = [k for k in shared if old[k].get(f) != new[k].get(f)]
        if bad:
            k = bad[0]
            fails.append(f"lambda-independent field {f}: {len(bad)} rows differ, "
                         f"first {k} {old[k].get(f)!r} -> {new[k].get(f)!r}")

    # 3. The grid is present and complete on every row.
    bad = [k for k in shared
           if set(new[k].get("g", {})) != {gk(l) for l in HUANG_GRID}
           or set(new[k].get("g_tra", {})) != {gk(l) for l in HUANG_GRID}]
    if bad:
        fails.append(f"{len(bad)} rows do not carry all {len(HUANG_GRID)} grid "
                     f"lambdas in both g and g_tra, first {bad[0]}")

    # 4. Selection self-consistency: the stored choice IS the max admissible of
    #    the stored g_tra, recomputed here rather than trusted.
    sel_bad, adm_bad, gsel_bad, near_bad = [], [], [], []
    for k in shared:
        r = new[k]
        t = r.get("g_tra", {})
        if set(t) != {gk(l) for l in HUANG_GRID}:
            continue
        adm = [l for l in HUANG_GRID if t[gk(l)] <= GTRA_MAX]
        want_sel = max(adm) if adm else None
        got_sel = r.get("selected_lambda")
        if (want_sel is None) != (got_sel is None) or (
                want_sel is not None and got_sel != want_sel):
            sel_bad.append((k, got_sel, want_sel))
        if bool(r.get("admissible")) != bool(adm):
            adm_bad.append(k)
        if got_sel is not None and r.get("g_selected") != r["g"].get(gk(got_sel)):
            gsel_bad.append(k)
        want_near = sum(1 for l in HUANG_GRID
                        if abs(t[gk(l)] - GTRA_MAX) < NEAR_BOUNDARY)
        if r.get("near_boundary_count") != want_near:
            near_bad.append((k, r.get("near_boundary_count"), want_near))
    if sel_bad:
        k, got, want = sel_bad[0]
        fails.append(f"selected_lambda is not the largest admissible on "
                     f"{len(sel_bad)} rows, first {k}: {got!r} against {want!r}")
    if adm_bad:
        fails.append(f"admissible flag disagrees with the stored g_tra on "
                     f"{len(adm_bad)} rows, first {adm_bad[0]}")
    if gsel_bad:
        fails.append(f"g_selected is not g at the selected lambda on "
                     f"{len(gsel_bad)} rows, first {gsel_bad[0]}")
    if near_bad:
        k, got, want = near_bad[0]
        fails.append(f"near_boundary_count wrong on {len(near_bad)} rows, "
                     f"first {k}: {got!r} against {want!r}")

    # 5. A row selecting lambda = 0.1 must reproduce the FROZEN 0.1 value
    #    exactly. D16 section 9's second clause: same quantity, same lambda.
    bad = [k for k in shared
           if new[k].get("selected_lambda") == 0.1
           and new[k].get("g_selected") != old[k]["g"]["0.1"]]
    if bad:
        fails.append(f"{len(bad)} rows select lambda = 0.1 but their g_selected "
                     f"differs from the frozen 0.1 column, first {bad[0]}")

    # 6. Both monotonicity directions, on the real data, per the D16 amendment
    #    of 8 October 2026. The worst relative violation is reported on every
    #    run, pass or fail, so a tolerance cannot hide behind a silent PASS.
    tra_big, tra_near, gen_big = [], [], []
    worst_tra, worst_gen, nearest = 0.0, 0.0, float("inf")
    for k in shared:
        r = new[k]
        t = [r["g_tra"][gk(l)] for l in HUANG_GRID] if r.get("g_tra") else []
        g = [r["g"][gk(l)] for l in HUANG_GRID] if r.get("g") else []
        if len(t) == len(HUANG_GRID):
            for a, b in zip(t, t[1:]):
                if b < a:
                    scale = max(abs(a), abs(b)) or 1.0
                    rel = (a - b) / scale
                    worst_tra = max(worst_tra, rel)
                    near = min(abs(a - GTRA_MAX), abs(b - GTRA_MAX))
                    nearest = min(nearest, near)
                    if rel > MONO_REL_TOL:
                        tra_big.append((k, rel))
                    if near < MONO_THRESH_GUARD:
                        tra_near.append((k, near))
        if len(g) == len(HUANG_GRID):
            for a, b in zip(g, g[1:]):
                if b > a:
                    scale = max(abs(a), abs(b)) or 1.0
                    worst_gen = max(worst_gen, (b - a) / scale)
                    gen_big.append(k)
    if tra_big:
        k, rel = max(tra_big, key=lambda z: z[1])
        fails.append(f"g_tra decreases in lambda by more than the declared "
                     f"{MONO_REL_TOL:g} relative tolerance on {len(tra_big)} "
                     f"instances, worst {rel:.3e} at {k}. Above rounding; treat "
                     f"as a defect.")
    if tra_near:
        k, near = min(tra_near, key=lambda z: z[1])
        fails.append(f"{len(tra_near)} monotonicity violations involve a value "
                     f"within {MONO_THRESH_GUARD:g} of the {GTRA_MAX} threshold, "
                     f"nearest {near:.3e} at {k}. Rounding could then change an "
                     f"admissibility decision, so the run is invalid.")
    if gen_big:
        fails.append(f"g_gen is not non-increasing in lambda on {len(gen_big)} "
                     f"instances, worst {worst_gen:.3e} relative. D16 section "
                     f"10's proof rests on this, so a violation invalidates the "
                     f"prediction as well as the run.")

    # 7. Validity flag.
    bad = [k for k in shared if not new[k].get("valid", False)]
    if bad:
        fails.append(f"{len(bad)} rows are marked not valid (non-finite g or "
                     f"g_tra), first {bad[0]}. Per D16 section 7 the column is "
                     f"then INCOMPLETE.")

    if verbose:
        print(f"\n  gate: {len(old)} frozen rows, {len(new)} new rows, "
              f"{len(shared)} shared keys")
        if fails:
            print(f"\n  FAIL. {len(fails)} problem(s). The run is INVALID and "
                  f"nothing may be read from it.\n")
            for f in fails:
                print(f"    - {f}")
            print()
        else:
            print(f"    [PASS] all four frozen columns bit-identical")
            print(f"    [PASS] all {len(INVARIANT)} lambda-independent fields identical")
            print(f"    [PASS] every row carries all {len(HUANG_GRID)} grid lambdas")
            print(f"    [PASS] selected_lambda == max admissible, recomputed")
            print(f"    [PASS] g_selected == g at the selected lambda")
            print(f"    [PASS] rows selecting 0.1 match the frozen 0.1 column")
            print(f"    [PASS] g_gen non-increasing, every row "
                  f"(worst rise {worst_gen:.3e} relative)")
            print(f"    [PASS] g_tra monotonicity within the declared "
                  f"{MONO_REL_TOL:g} tolerance")
            print(f"           worst relative decrease {worst_tra:.3e}; nearest "
                  f"violating value to {GTRA_MAX} is "
                  f"{(nearest if nearest < float('inf') else float('nan')):.3e} "
                  f"(guard {MONO_THRESH_GUARD:g})")
            print(f"    [PASS] every row finite")
            print("\n  gate PASSED. The run is valid.\n")
    return not fails


def branch(old, new):
    """Which pre-committed outcome obtained. Reads selected values."""
    rows = [new[k] for k in sorted(new)]
    inadmissible = [r for r in rows if not r.get("admissible")]
    admissible = [r for r in rows if r.get("admissible")]
    near_total = sum(int(r.get("near_boundary_count") or 0) for r in rows)
    breaches = [r for r in admissible
                if float(r["g_selected"]) > float(r["ceiling"])]

    print(f"  rows                     : {len(rows)}")
    print(f"  admissible (g_tra rule)  : {len(admissible)}")
    print(f"  INADMISSIBLE             : {len(inadmissible)}")
    print(f"  within {NEAR_BOUNDARY:g} of 0.045    : {near_total}  "
          f"(the only population where '<' could differ from '<=')")

    dist = Counter(r.get("selected_lambda") for r in rows)
    print("\n  selected lambda:")
    for lam in list(HUANG_GRID) + [None]:
        if dist.get(lam):
            label = "none (inadmissible)" if lam is None else f"{lam:g}"
            print(f"    {label:<22} {dist[lam]:>6}")

    # The prediction in D16 section 10, checked rather than assumed.
    frozen_breach = {k for k in old
                     if float(old[k]["g"]["0.1"]) > float(old[k]["ceiling"])}
    print(f"\n  D16 section 10 predicted: every row breaching at lambda = 0.1 "
          f"breaches under this rule.")
    print(f"    rows breaching at the frozen 0.1 : {len(frozen_breach)}")
    missed = [k for k in frozen_breach
              if k in new and new[k].get("admissible")
              and not (float(new[k]["g_selected"]) > float(new[k]["ceiling"]))]
    unresolved = [k for k in frozen_breach if k in new and not new[k].get("admissible")]
    print(f"    of those, breaching here         : "
          f"{len(frozen_breach) - len(missed) - len(unresolved)}")
    print(f"    of those, inadmissible so no g   : {len(unresolved)}")
    if missed:
        print(f"    PREDICTION VIOLATED on {len(missed)} rows, first {missed[0]}.")
        print(f"    This contradicts a theorem, so the implementation is the")
        print(f"    first suspect, not the proof.")

    print(f"\n  breaches among admissible rows : {len(breaches)} / {len(admissible)}")

    if inadmissible:
        print("\n  -> B3. The column is INCOMPLETE: Huang's rule is not satisfiable")
        print("     on every row and no fallback lambda is substituted. Option (b)")
        print("     is reported as UNRESOLVED, and the inadmissibility itself is")
        print("     the finding. No verdict is drawn from a partial column.\n")
        return "B3"
    if breaches:
        print("\n  -> B2. Complete and valid, with breaches. NOT ESTABLISHED stands")
        print("     and its scope widens from two evaluated lambda rules to three.")
        print("     No other paper text changes.\n")
        return "B2"
    print("\n  -> B1, WHICH D16 SECTION 10 EXCLUDED IN ADVANCE.")
    print("     g_gen is non-increasing in lambda and the grid tops out at 0.1,")
    print("     so every row breaching at 0.1 must breach here. A breach-free")
    print("     column contradicts that. Per D16, the run is INVALID pending")
    print("     resolution: the implementation is the first suspect.\n")
    return "B1"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frozen", default="results/audits/g_units.jsonl")
    ap.add_argument("--new", default="results/audits/g_units_gtra.jsonl")
    ap.add_argument("--branch", action="store_true",
                    help="after the gate passes, report which pre-committed "
                         "outcome obtained. This reads selected values.")
    a = ap.parse_args()

    old, new = load(a.frozen), load(a.new)
    if not gate(old, new):
        raise SystemExit(1)
    if a.branch:
        branch(old, new)
    else:
        print("  Gate only. Re-run with --branch to read the outcome.\n")


if __name__ == "__main__":
    main()
