#!/usr/bin/env python3
"""The integrity gate for D14's option-(a) re-run. Section 8 of the decision.

WHY THIS EXISTS
---------------
D14's decision of 4 October 2026 changes `lambda_from_svm_C` from 1/(2*C*n) to
1/(2*C). Only the `from_C` column may move. The four frozen columns
{1e-1, 1e-2, 1e-3, 1e-4} are computed at hardcoded lambdas and must come back
bit-identical, and `d_normap` does not depend on lambda at all.

So the re-run is also a determinism test across the whole sweep, for free. If any
frozen column or any lambda-independent field differs at any of 7,200 rows, the
re-run is INVALID: nothing is read from it and the difference is a defect to
investigate. That gate is stated in the decision record before the run, and this
script is the gate.

The gate deliberately prints NO value of the recomputed from_C column. Reading
one is a separate step behind --branch, which refuses to run unless the gate has
passed in the same invocation.

Usage:
    python scripts/check_lam2c_rerun.py
    python scripts/check_lam2c_rerun.py --branch     # gate, then the branch
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

FROZEN = ("0.1", "0.01", "0.001", "0.0001")

# Fields that cannot depend on lambda. Any movement here is a defect, not a
# consequence of the change.
INVARIANT = ("d_normap", "ceiling", "classical_C", "classical_method",
             "quantum_bandwidth", "n_qubits", "arm")

KEY = ("arm", "dataset", "n_per_class", "mapping", "n_qubits", "setting", "seed")


def load(path):
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"\n  {p} does not exist.\n")
    out = {}
    for i, line in enumerate(p.open(), 1):
        if not line.strip():
            continue
        r = json.loads(line)
        k = tuple(r.get(f) for f in KEY)
        if k in out:
            raise SystemExit(f"\n  {p} line {i}: duplicate key {k}\n")
        out[k] = r
    return out


def gate(old, new, verbose=True):
    """True only if the re-run is valid. Prints every class of failure found."""
    fails = []

    if len(new) != len(old):
        fails.append(f"row count: {len(new)} new against {len(old)} old")

    missing = sorted(set(old) - set(new))
    extra = sorted(set(new) - set(old))
    if missing:
        fails.append(f"{len(missing)} keys absent from the re-run, first {missing[0]}")
    if extra:
        fails.append(f"{len(extra)} keys only in the re-run, first {extra[0]}")

    shared = sorted(set(old) & set(new))

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

    inv_bad = {f: 0 for f in INVARIANT}
    first = {}
    for k in shared:
        for f in INVARIANT:
            if old[k].get(f) != new[k].get(f):
                inv_bad[f] += 1
                first.setdefault(f, (k, old[k].get(f), new[k].get(f)))
    for f, n in inv_bad.items():
        if n:
            k, a, b = first[f]
            fails.append(f"lambda-independent field {f}: {n} rows differ, "
                         f"first {k} {a!r} -> {b!r}")

    # The new rule, asserted on the stored field rather than trusted.
    lam_bad = []
    for k in shared:
        c = float(new[k]["classical_C"])
        want = 1.0 / (2.0 * c)
        got = float(new[k]["lambda_from_C"])
        if got != want:
            lam_bad.append((k, got, want))
    if lam_bad:
        k, got, want = lam_bad[0]
        fails.append(f"lambda_from_C is not 1/(2C) on {len(lam_bad)} rows, "
                     f"first {k}: {got!r} against {want!r}")

    if verbose:
        print(f"\n  gate: {len(old)} old rows, {len(new)} new rows, "
              f"{len(shared)} shared keys")
        if fails:
            print(f"\n  FAIL. {len(fails)} problem(s). The re-run is INVALID and "
                  f"nothing may be read from it.\n")
            for f in fails:
                print(f"    - {f}")
            print()
        else:
            print("    [PASS] all four frozen columns bit-identical")
            print(f"    [PASS] all {len(INVARIANT)} lambda-independent fields identical")
            print("    [PASS] lambda_from_C == 1/(2C) on every row")
            print("\n  gate PASSED. The re-run is valid.\n")
    return not fails


def branch(new):
    """Which of D14's pre-committed outcomes obtained. Reads from_C values."""
    rows = list(new.values())
    breaches = [r for r in rows if float(r["g_from_C"]) > float(r["ceiling"])]
    gs = [float(r["g_from_C"]) for r in rows]
    distinct = len(set(gs))
    ties = 1.0 - distinct / len(gs)

    print(f"  from_C ceiling breaches: {len(breaches)} / {len(rows)} rows")
    print(f"  distinct g_from_C values: {distinct}  (tie fraction {ties:.4f})")

    if breaches:
        print("\n  -> O2. `clean` stays empty. H2 and H3 remain NOT ESTABLISHED.")
        print("     No paper text changes beyond closing D14 and extending 3.9.\n")
        return "O2"
    if distinct == 1:
        print("\n  -> O3. g_from_C is constant, so the rank correlation is")
        print("     undefined. Reported as a measurement. NO verdict is claimed.\n")
        return "O3"
    print("\n  -> O1. `clean` = {from_C}. The registered D5 rule yields a verdict")
    print("     on this column, and that verdict is PRIMARY for H2 and H3")
    print("     whatever its sign. Run geometric_tests.py --test against the new")
    print("     units file to compute it, then rewrite 1.2, 6.1 and 6.5.")
    print("     Heavy ties short of constancy are reported, not treated as O3.\n")
    return "O1"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", default="results/audits/g_units.jsonl")
    ap.add_argument("--new", default="results/audits/g_units_lam2c.jsonl")
    ap.add_argument("--branch", action="store_true",
                    help="after the gate passes, report which pre-committed "
                         "outcome obtained. This reads recomputed g values.")
    a = ap.parse_args()

    ok = gate(load(a.old), load(a.new))
    if not ok:
        raise SystemExit(1)
    if a.branch:
        branch(load(a.new))
    else:
        print("  Gate only. Re-run with --branch to read the outcome.\n")


if __name__ == "__main__":
    main()
