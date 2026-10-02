#!/usr/bin/env python3
"""The four registered exploratory families that had no output.

Section 9 of the pre-registration names five exploratory families:

    "the 15-cell sweep per dataset, the qubit-count trend, the learning curve,
     the training-size comparison, per-mapping breakdowns"

Two of them already exist, Holm-corrected, in `scripts/primary_tests.py`
(`report_sweep` and `report_per_setting`), printed to
`results/analysis/primary_tests.log`. This script implements the other four and
writes them as structured output, because a table that exists only in a stdout
capture cannot be checked against a paper.

WHAT THIS SCRIPT DOES NOT DO. It computes no geometric difference, reads no
lambda, and touches nothing D14 gates. The families here are paired normAP and
ROC-AUC differences over cells, qubit counts, mappings and training sizes. No
output of this script can move H1, H2 or H3, and section 9 forbids any
exploratory finding being described as evidence for or against them.

THE AGGREGATION, AND WHY IT IS THIS ONE. Week 4 item 10 records a defect worth
not repeating: `trend_stats` correlated over all 300 records rather than the 15
cells, "treating twenty seeds of one configuration as twenty independent
observations of a trend across cells", and the record states that "the
cell-level figures, n = 15, are the ones this record reports; every row-level
figure printed before the fix is void."

The same hazard applies here. At one qubit count there are three mappings, and
at one seed those three share a train/test split, because `make_split` is keyed
on the seed alone. Three cells at a qubit count are therefore not three
independent observations. So:

  * for a per-level test, the three (or five) cells at that level are averaged
    WITHIN each seed first, giving 20 properly paired observations per level;
  * for a trend statistic, the unit is the cell, n = 15, never the row.

Both are stated in the output so a reader does not have to infer them.

DECLARED POST-HOC. The form of these four families was fixed on 1 October 2026,
after the data existed. Section 9 registers the families by name and does not
specify their form; section 11 requires a choice made after results are seen to
be declared as such. These are exploratory by registration, so no confirmatory
verdict depends on the choice.

Usage:
    PYTHONPATH=src python scripts/exploratory_sweep.py --check
    PYTHONPATH=src python scripts/exploratory_sweep.py \
        --out results/analysis/exploratory_sweep.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from primary_tests import (  # noqa: E402
    ALPHA, CLASSICAL_KERNELS, CONFIRMATORY_N, PRIMARY_CELL,
    best_by_inner, endpoint_test, fmt_p, holm, integrity, load, norm_ap)

SIZES = (50, 100, 250)
QUBITS = (4, 6, 8, 10, 12)
MAPPINGS = ("pca", "randproj", "selectk")
DATASETS = ("churn", "fraud")

# Pre-registration line 104: the 50-per-class arm "is run for the shape of the
# learning curve and is NOT used for hypothesis testing". Enforced here rather
# than remembered.
NO_TEST_SIZES = (50,)

EXPL = "EXPLORATORY"


# --------------------------------------------------------------- loading

def arm(dataset, n_per_class, q_dir, c_dir):
    """(q_by_cell, c_by_cell, seeds, notes) or (None, None, None, [why])."""
    qpath = q_dir / f"{dataset}_matched_n{n_per_class}.jsonl"
    cpath = c_dir / f"{dataset}_matched_n{n_per_class}.jsonl"
    qrecs, crecs = load(qpath), load(cpath)
    if qrecs is None:
        return None, None, None, [f"missing {qpath.name}"]
    if crecs is None:
        return None, None, None, [f"missing {cpath.name}"]
    fatal, notes, q_by_cell, c_by_cell, _is_arm = integrity(
        qrecs, crecs, dataset, n_per_class)
    if fatal:
        return None, None, None, [f"integrity: {f}" for f in fatal]
    seeds = sorted({r["seed"] for r in qrecs})
    return q_by_cell, c_by_cell, seeds, notes


def cell_diffs(q_by_cell, c_by_cell, seeds):
    """{(mapping, qubits): {seed: (d_normap, d_roc)}} -- best-of-four minus
    best-of-three, per seed, for every cell present."""
    out = {}
    for (m, nq, seed), qs in q_by_cell.items():
        cs = c_by_cell.get((m, nq, seed))
        if not qs or not cs:
            continue
        q = best_by_inner(qs)
        c = best_by_inner([r for r in cs if r["method"] in CLASSICAL_KERNELS])
        out.setdefault((m, nq), {})[seed] = (
            norm_ap(q) - norm_ap(c),
            float(q["test_roc_auc"]) - float(c["test_roc_auc"]),
        )
    return out


# --------------------------------------------------------------- helpers

def seed_means(diffs, cells, seeds, idx=0):
    """Average the given cells WITHIN each seed. Returns one value per seed.

    This is the step that keeps the pairing honest: cells at the same seed
    share a train/test split, so they are averaged before any test rather than
    pooled as independent observations.
    """
    vals = []
    for seed in seeds:
        xs = [diffs[c][seed][idx] for c in cells
              if c in diffs and seed in diffs[c]]
        if xs:
            vals.append(float(np.mean(xs)))
    return vals


def tested_family(label, levels, series_by_level, note):
    """Wilcoxon per level, Holm within the family. Returns a JSON-able dict."""
    rows, praw = [], []
    for lv in levels:
        s = series_by_level.get(lv) or []
        if len(s) < 2:
            rows.append({"level": lv, "n": len(s), "estimable": False,
                         "why": "fewer than 2 paired observations"})
            continue
        e = endpoint_test(s)
        rows.append({"level": lv, "n": e["n"], "estimable": True,
                     "mean": e["mean"], "median": e["median"],
                     "ci": list(e["ci"]), "p_wilcoxon": e["p_wilcoxon"],
                     "p_t": e["p_t"]})
        praw.append(e["p_wilcoxon"])
    adj = holm(praw) if praw else []
    it = iter(adj)
    for r in rows:
        if r.get("estimable"):
            r["p_holm"] = next(it)
            r["rejects_after_holm"] = bool(r["p_holm"] < ALPHA)
    return {"family": label, "caption": f"{EXPL}: {label} "
            f"(Holm-corrected within this family of {len(praw)}; "
            f"bears on no confirmatory hypothesis)",
            "aggregation": note, "rows": rows}


def print_tested(fam):
    print(f"\n  {fam['caption']}")
    print(f"    {fam['aggregation']}")
    print(f"    {'level':<12}{'n':>4}{'mean dNormAP':>15}{'p':>12}{'Holm':>12}")
    for r in fam["rows"]:
        if not r.get("estimable"):
            print(f"    {str(r['level']):<12}{r['n']:>4}   not estimable: {r['why']}")
            continue
        star = "  *" if r["rejects_after_holm"] else ""
        print(f"    {str(r['level']):<12}{r['n']:>4}{r['mean']:>+15.4f}"
              f"{fmt_p(r['p_wilcoxon']):>12}{fmt_p(r['p_holm']):>12}{star}")


# --------------------------------------------------------------- families

def family_qubit_trend(diffs, seeds):
    """Family 1: the qubit-count trend. Five levels, plus a cell-level trend."""
    series = {nq: seed_means(diffs, [(m, nq) for m in MAPPINGS], seeds)
              for nq in QUBITS}
    fam = tested_family(
        "the qubit-count trend", list(QUBITS), series,
        "per level: the three mappings averaged within each seed, then "
        "Wilcoxon over seeds. Cells at one seed share a split.")
    # The trend statistic, on cells. n = 15, per week 4 item 10.
    pts = [(nq, float(np.mean([v[0] for v in diffs[(m, nq)].values()])))
           for m in MAPPINGS for nq in QUBITS if (m, nq) in diffs]
    if len(pts) >= 3:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        if len(set(xs)) > 1 and len(set(ys)) > 1:
            rho, p = stats.spearmanr(xs, ys)
            fam["cell_level_trend"] = {
                "unit": "cell", "n_cells": len(pts),
                "spearman_rho": float(rho), "p": float(p),
                "note": "unit is the cell, not the record. Week 4 item 10 "
                        "voided every row-level trend figure."}
        else:
            fam["cell_level_trend"] = {"unit": "cell", "n_cells": len(pts),
                                       "spearman_rho": None, "p": None,
                                       "note": "constant input; undefined"}
    return fam


def family_per_mapping(diffs, seeds):
    """Family 2: per-mapping breakdowns. Three levels."""
    series = {m: seed_means(diffs, [(m, nq) for nq in QUBITS], seeds)
              for m in MAPPINGS}
    return tested_family(
        "per-mapping breakdowns", list(MAPPINGS), series,
        "per level: the five qubit counts averaged within each seed, then "
        "Wilcoxon over seeds.")


def family_training_size(by_size, seeds_by_size):
    """Family 3: the training-size comparison. n=50 is reported, not tested."""
    series, levels = {}, []
    for n in SIZES:
        if n not in by_size:
            continue
        levels.append(n)
        series[n] = seed_means(by_size[n],
                               list(by_size[n].keys()), seeds_by_size[n])
    testable = [n for n in levels if n not in NO_TEST_SIZES]
    fam = tested_family(
        "the training-size comparison", testable,
        {n: series[n] for n in testable},
        "per level: all 15 cells averaged within each seed, then Wilcoxon over "
        "seeds. The 50-per-class arm is EXCLUDED from testing by "
        "pre-registration line 104 and is reported descriptively below.")
    fam["descriptive_only"] = [
        {"level": n, "n_seeds": len(series[n]),
         "mean_d_normap": float(np.mean(series[n])) if series[n] else None,
         "why_not_tested": "pre-registration line 104: run for the shape of "
                           "the learning curve, not for hypothesis testing"}
        for n in levels if n in NO_TEST_SIZES]
    return fam


def family_learning_curve(raw_by_size):
    """Family 4: the learning curve. Descriptive, in week 3 section 9's form.

    Week 3 section 9 reports "best cell per training size, corrected normAP".
    That form is kept so the quantum arm is directly comparable to the
    classical table already published, and no p-value is attached to it. The
    testable version of the same question is family 3.
    """
    rows = []
    for n in SIZES:
        got = raw_by_size.get(n)
        if not got:
            continue
        q_by_cell, c_by_cell, seeds = got
        best_q = best_c = None
        for (m, nq) in sorted({(a, b) for (a, b, _) in q_by_cell}):
            qv, cv = [], []
            for seed in seeds:
                qs = q_by_cell.get((m, nq, seed))
                cs = c_by_cell.get((m, nq, seed))
                if not qs or not cs:
                    continue
                qv.append(norm_ap(best_by_inner(qs)))
                cv.append(norm_ap(best_by_inner(
                    [r for r in cs if r["method"] in CLASSICAL_KERNELS])))
            if qv:
                mq = float(np.mean(qv))
                if best_q is None or mq > best_q[1]:
                    best_q = ((m, nq), mq)
            if cv:
                mc = float(np.mean(cv))
                if best_c is None or mc > best_c[1]:
                    best_c = ((m, nq), mc)
        rows.append({
            "n_per_class": n,
            "best_quantum_cell": list(best_q[0]) if best_q else None,
            "best_quantum_normap": best_q[1] if best_q else None,
            "best_classical_cell": list(best_c[0]) if best_c else None,
            "best_classical_normap": best_c[1] if best_c else None,
        })
    return {"family": "the learning curve",
            "caption": f"{EXPL}: the learning curve, best cell per training "
                       f"size, corrected normAP. Descriptive, in week 3 "
                       f"section 9's form; no p-value is attached. The "
                       f"testable form of this question is the training-size "
                       f"comparison.",
            "aggregation": "best cell by mean normAP over seeds, each arm "
                           "selected independently",
            "rows": rows}


# ------------------------------------------------------------------ main

def check(q_dir, c_dir):
    """Validate inputs and interfaces. Computes no difference and prints no g,
    no breach count and no verdict. Exits non-zero on any problem."""
    print("input check. No difference, trend or p-value is computed here.\n")
    bad = 0
    for ds in DATASETS:
        for n in SIZES:
            q_by_cell, c_by_cell, seeds, notes = arm(ds, n, q_dir, c_dir)
            if q_by_cell is None:
                print(f"  FAIL {ds:>6} n={n:<4} {notes[0]}")
                bad += 1
                continue
            cells = sorted({(m, nq) for (m, nq, _) in q_by_cell})
            exp_cells = [(m, nq) for m in MAPPINGS for nq in QUBITS]
            missing = [c for c in exp_cells if c not in cells]
            extra = [c for c in cells if c not in exp_cells]
            ok = not missing and not extra and len(seeds) == 20
            print(f"  {'ok  ' if ok else 'WARN'} {ds:>6} n={n:<4} "
                  f"cells={len(cells):<3} seeds={len(seeds):<3}")
            if missing:
                print(f"       missing cells: {missing}")
                bad += 1
            if extra:
                print(f"       unexpected cells: {extra}")
                bad += 1
            if len(seeds) != 20:
                print(f"       seed count is {len(seeds)}, expected 20")
                bad += 1
    print(f"\n  primary cells (not used by these families): {PRIMARY_CELL}")
    print(f"  confirmatory n (not used by these families): {CONFIRMATORY_N}")
    print(f"  sizes excluded from testing: {NO_TEST_SIZES}")
    print(f"\n{'inputs are complete' if not bad else f'{bad} problem(s)'}")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="validate inputs only; compute nothing")
    ap.add_argument("--dataset", choices=sorted(DATASETS))
    ap.add_argument("--quantum-dir",
                    default=str(ROOT / "results" / "runs" / "quantum"))
    ap.add_argument("--classical-dir",
                    default=str(ROOT / "results" / "runs" / "classical"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    q_dir, c_dir = Path(args.quantum_dir), Path(args.classical_dir)
    if args.check:
        sys.exit(check(q_dir, c_dir))

    datasets = (args.dataset,) if args.dataset else DATASETS
    report = {"declared": "post-hoc, 1 October 2026; form fixed after the data "
                          "existed; exploratory by section 9",
              "alpha": ALPHA, "datasets": {}}
    worst = 0

    for ds in datasets:
        print(f"\n{'=' * 74}\n{ds}\n{'=' * 74}")
        raw_by_size, diff_by_size, seeds_by_size = {}, {}, {}
        for n in SIZES:
            q_by_cell, c_by_cell, seeds, notes = arm(ds, n, q_dir, c_dir)
            if q_by_cell is None:
                print(f"  SKIPPED n={n}: {notes[0]}")
                worst = max(worst, 1)
                continue
            raw_by_size[n] = (q_by_cell, c_by_cell, seeds)
            diff_by_size[n] = cell_diffs(q_by_cell, c_by_cell, seeds)
            seeds_by_size[n] = seeds

        if CONFIRMATORY_N not in diff_by_size:
            print(f"  cannot build the qubit or mapping families without "
                  f"n={CONFIRMATORY_N}")
            worst = max(worst, 1)
            continue

        d250, s250 = diff_by_size[CONFIRMATORY_N], seeds_by_size[CONFIRMATORY_N]
        fams = [family_qubit_trend(d250, s250),
                family_per_mapping(d250, s250),
                family_training_size(diff_by_size, seeds_by_size),
                family_learning_curve(raw_by_size)]

        for fam in fams[:3]:
            print_tested(fam)
            if "cell_level_trend" in fam:
                t = fam["cell_level_trend"]
                r = "undefined" if t["spearman_rho"] is None else \
                    f"rho {t['spearman_rho']:+.4f}  p {fmt_p(t['p'])}"
                print(f"    cell-level trend (n={t['n_cells']} cells): {r}")
            if fam.get("descriptive_only"):
                for r in fam["descriptive_only"]:
                    m = r["mean_d_normap"]
                    print(f"    n={r['level']} reported not tested: mean "
                          f"dNormAP {m:+.4f} over {r['n_seeds']} seeds"
                          if m is not None else
                          f"    n={r['level']} reported not tested: no data")

        lc = fams[3]
        print(f"\n  {lc['caption']}")
        print(f"    {'n/class':<9}{'best quantum':>22}{'best classical':>24}")
        for r in lc["rows"]:
            q = f"{tuple(r['best_quantum_cell'])} {r['best_quantum_normap']:.4f}" \
                if r["best_quantum_cell"] else "--"
            c = f"{tuple(r['best_classical_cell'])} {r['best_classical_normap']:.4f}" \
                if r["best_classical_cell"] else "--"
            print(f"    {r['n_per_class']:<9}{q:>22}{c:>24}")

        report["datasets"][ds] = {f["family"]: f for f in fams}

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, default=float) + "\n")
        print(f"\n-> {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")

    print("\nEvery table above is exploratory. Section 9: no exploratory "
          "finding is evidence for or against H1 or H2.")
    sys.exit(worst)


if __name__ == "__main__":
    main()
