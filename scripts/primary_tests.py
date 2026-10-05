#!/usr/bin/env python3
"""H1, exactly as section 4 of the pre-registration writes it, and nothing else.

WHAT THIS DOES, AND WHAT IT REFUSES TO DO
-----------------------------------------
The quantum sweep is finished. There are now 7,200 quantum records sitting
next to 5,400 classical ones, and 15 cells per file each of which will show
some difference. The way this literature goes wrong is by looking at all of
them and then deciding which one was the test.

So this script runs the pre-registered test first, in the pre-registered cell,
by the pre-registered rule, and prints its verdict before it prints anything
else. Everything after that is labelled exploratory and none of it can change
the verdict.

THE REGISTERED RULE (section 4)
-------------------------------
  * Primary cell: churn = PCA at 12 qubits, fraud = SelectKBest at 8.
  * 250 points per class. The 50-per-class arm was declared underpowered in
    advance (MDE 0.0427 on churn) and carries no hypothesis; 100 is reported
    as a learning curve.
  * Two co-primary endpoints, normAP and ROC-AUC, from the same stored scores.
  * INTERSECTION-UNION: reject only if BOTH endpoints reject at alpha 0.05,
    two-sided. No alpha correction, because the type I error of "reject only
    if both reject" is at most that of either test alone.
  * Wilcoxon signed-rank on the 20 paired per-seed differences. The paired
    t-test is reported alongside as a sensitivity check, never as the test.
  * Best-quantum-of-four against best-classical-of-three, both selected by
    INNER-CV average precision on training folds only. The outer test score
    is never consulted for selection, here or anywhere.

INTEGRITY FIRST, AND IT CAN HALT
--------------------------------
Section 4 says records are paired on the test-label fingerprint and that a
mismatch aborts the analysis rather than being worked around. That is enforced
here: if any quantum record's test labels differ from the classical record it
would be paired with, this script prints the offending cells and exits
non-zero WITHOUT running a test. The same for a run on the wrong backend, a
shuffled record in a real-labels file, or a non-converged final model.

Usage:
    PYTHONPATH=src python scripts/primary_tests.py --dataset churn
    PYTHONPATH=src python scripts/primary_tests.py --all
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics as st
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qbench.metrics import normalised_average_precision  # noqa: E402

ALPHA = 0.05

# Section 3 of the pre-registration. Named before any quantum kernel ran.
PRIMARY_CELL = {"churn": ("pca", 12), "fraud": ("selectk", 8)}

# Section 5, the intersection-union column. Used only to state the exclusion
# bound when the test does not reject; never to decide whether it rejects.
MDE_IU = {("churn", 250): 0.0171, ("churn", 100): 0.0298, ("churn", 50): 0.0427,
          ("fraud", 250): 0.0059, ("fraud", 100): 0.0094, ("fraud", 50): 0.0163}

CONFIRMATORY_N = 250
REGISTERED_DEVICE = "lightning.qubit"
CLASSICAL_KERNELS = ("linear", "rbf", "poly")


# ------------------------------------------------------------ provenance

def git_commit():
    """Short HEAD, or None if this is not a checkout.

    `rev-parse` is read-only and does not touch `.git/index`, unlike
    `git status`, which refreshes and rewrites it.
    """
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True,
            stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def file_provenance(path):
    """Path, size and SHA-256 of an input, so a stored result names what it read."""
    p = Path(path)
    if not p.exists():
        return {"path": str(p), "present": False}
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    rel = str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
    return {"path": rel, "present": True, "bytes": p.stat().st_size,
            "sha256": h.hexdigest()}


# ---------------------------------------------------------------- loading

def load(path):
    if not path.exists():
        return None
    out = []
    for line in path.open():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def cell_key(r):
    return (r["mapping"], r["n_qubits"], r["seed"])


def best_by_inner(records):
    """Highest inner-CV average precision, ties broken by method name.

    Deterministic on purpose: a tie broken by dict order would make the
    analysis depend on file order, and file order depends on which cells were
    resumed. `method` is unique within a (cell, seed) group.
    """
    return sorted(records, key=lambda r: (-round(float(r["inner_score"]), 12), r["method"]))[0]


def norm_ap(r):
    n = int(r["n_test"])
    p = int(round(float(r["test_base_rate"]) * n))
    return normalised_average_precision(float(r["test_average_precision"]), n, p)


# ------------------------------------------------------------- integrity

def integrity(qrecs, crecs, dataset, n_per_class):
    """Everything that must hold before a test is allowed to run.

    Returns a list of fatal problems. An empty list means the pairing is sound.
    """
    fatal, notes = [], []

    arm = [r for r in qrecs if r.get("bandwidth_arm")]
    if arm:
        bws = Counter(r.get("bandwidth") for r in qrecs)
        notes.append("EXPLORATORY BANDWIDTH ARM (deviations D4): no verdict from this "
                     "file is confirmatory, whatever flags were passed.")
        notes.append(f"  inner CV selected bandwidths: "
                     f"{dict(sorted(bws.items(), key=lambda kv: -kv[1]))}")

    shuffled = [r for r in qrecs if r.get("shuffled")]
    if shuffled:
        fatal.append(f"{len(shuffled)} shuffled-label records in a real-labels file")

    devices = Counter(r.get("device") for r in qrecs)
    if set(devices) != {REGISTERED_DEVICE}:
        fatal.append(f"backend is not the registered one: {dict(devices)}")

    commits = Counter(r.get("git_commit") for r in qrecs)
    notes.append(f"quantum records written at commit(s): "
                 f"{', '.join(f'{c} x{n}' for c, n in commits.most_common())}")

    bad = [r for r in qrecs if not r.get("final_converged", True)]
    if bad:
        fatal.append(f"{len(bad)} quantum records whose final model did not converge")
    fell_back = sum(1 for r in qrecs if r.get("final_fallback_rank", 0) > 0)
    if fell_back:
        notes.append(f"{fell_back} quantum records used a fallback setting after a "
                     f"non-converged first choice")

    # Pairing. Section 4: assert, do not assume.
    q_by_cell, c_by_cell = defaultdict(list), defaultdict(list)
    for r in qrecs:
        q_by_cell[cell_key(r)].append(r)
    for r in crecs:
        if r.get("track") == "matched":
            c_by_cell[cell_key(r)].append(r)

    missing = [k for k in q_by_cell if k not in c_by_cell]
    if missing:
        fatal.append(f"{len(missing)} quantum cells have no classical counterpart "
                     f"(first: {missing[0]})")

    mismatched = []
    for k, qs in q_by_cell.items():
        cs = c_by_cell.get(k)
        if not cs:
            continue
        prints = {r["test_label_fingerprint"] for r in qs} | {r["test_label_fingerprint"] for r in cs}
        if len(prints) != 1:
            mismatched.append(k)
    if mismatched:
        fatal.append(f"test-label fingerprint mismatch in {len(mismatched)} cells "
                     f"(first: {mismatched[0]}); records were scored on different "
                     f"points and cannot be paired")

    seeds = sorted({r["seed"] for r in qrecs})
    settings = sorted({r["setting"] for r in qrecs})
    notes.append(f"{len(qrecs)} quantum records: {len(q_by_cell) // max(len(seeds), 1)} cells "
                 f"x {len(seeds)} seeds x {len(settings)} settings {settings}")

    hw = sum(int(r.get("circuit_evaluations", 0)) for r in qrecs)
    sim = sum(int(r.get("simulator_executions", 0)) for r in qrecs)
    notes.append(f"cost: {hw:,} hardware-equivalent circuit evaluations; "
                 f"{sim:,} statevectors actually simulated "
                 f"({hw / max(sim, 1):.0f}x, and the paper reports the former)")

    return fatal, notes, q_by_cell, c_by_cell, bool(arm)


# ------------------------------------------------------------ the test

def paired_series(q_by_cell, c_by_cell, cell, seeds):
    """Per seed: best quantum of four minus best classical of three."""
    rows = []
    for seed in seeds:
        k = (cell[0], cell[1], seed)
        qs, cs = q_by_cell.get(k), c_by_cell.get(k)
        if not qs or not cs:
            continue
        q = best_by_inner(qs)
        c = best_by_inner([r for r in cs if r["method"] in CLASSICAL_KERNELS])
        rows.append({
            "seed": seed,
            "q_method": q["setting"], "c_method": c["method"],
            "d_normap": norm_ap(q) - norm_ap(c),
            "d_roc": float(q["test_roc_auc"]) - float(c["test_roc_auc"]),
            "q_normap": norm_ap(q), "c_normap": norm_ap(c),
            "q_roc": float(q["test_roc_auc"]), "c_roc": float(c["test_roc_auc"]),
        })
    return rows


def endpoint_test(diffs):
    """Wilcoxon (the test) and paired t (the sensitivity check)."""
    d = np.asarray(diffs, dtype=float)
    n = len(d)
    out = {"n": n, "mean": float(d.mean()), "median": float(np.median(d)),
           "sd": float(d.std(ddof=1)) if n > 1 else float("nan")}
    if n > 1 and out["sd"] > 0:
        se = out["sd"] / math.sqrt(n)
        half = stats.t.ppf(1 - ALPHA / 2, n - 1) * se
        out["ci"] = (out["mean"] - half, out["mean"] + half)
        out["p_t"] = float(stats.ttest_1samp(d, 0.0).pvalue)
    else:
        out["ci"], out["p_t"] = (float("nan"), float("nan")), float("nan")
    nz = d[d != 0]
    if len(nz) >= 1:
        out["p_wilcoxon"] = float(stats.wilcoxon(nz, alternative="two-sided").pvalue)
        out["n_nonzero"] = int(len(nz))
    else:
        out["p_wilcoxon"], out["n_nonzero"] = 1.0, 0
    return out


def holm(pvals):
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    adj, running = [0.0] * len(pvals), 0.0
    for rank, i in enumerate(order):
        running = max(running, (len(pvals) - rank) * pvals[i])
        adj[i] = min(1.0, running)
    return adj


# ------------------------------------------------------------- reporting

def fmt_p(p):
    return f"{p:.2e}" if p < 1e-3 else f"{p:.4f}"


def report_primary(dataset, n_per_class, rows, confirmatory):
    cell = PRIMARY_CELL[dataset]
    head = "CONFIRMATORY" if confirmatory else "EXPLORATORY (not a hypothesis test)"
    print(f"\n{'=' * 74}")
    print(f"H1 {head}: {dataset}, {cell[0]}/{cell[1]} qubits, {n_per_class} per class")
    print(f"{'=' * 74}")
    if not rows:
        print("  no paired seeds; nothing to test")
        return None

    ap = endpoint_test([r["d_normap"] for r in rows])
    roc = endpoint_test([r["d_roc"] for r in rows])

    for name, e in (("normAP", ap), ("ROC-AUC", roc)):
        print(f"\n  {name}: quantum - classical, {e['n']} paired seeds")
        print(f"    mean {e['mean']:+.4f}   95% CI [{e['ci'][0]:+.4f}, {e['ci'][1]:+.4f}]"
              f"   median {e['median']:+.4f}   sd {e['sd']:.4f}")
        print(f"    Wilcoxon p = {fmt_p(e['p_wilcoxon'])}    "
              f"(paired t p = {fmt_p(e['p_t'])}, sensitivity only)")
        print(f"    rejects at alpha {ALPHA}: {'YES' if e['p_wilcoxon'] < ALPHA else 'no'}")

    both = ap["p_wilcoxon"] < ALPHA and roc["p_wilcoxon"] < ALPHA
    agree = (ap["mean"] > 0) == (roc["mean"] > 0)
    mde = MDE_IU.get((dataset, n_per_class))

    print(f"\n  INTERSECTION-UNION VERDICT: ", end="")
    if both and agree:
        direction = "quantum" if ap["mean"] > 0 else "classical"
        print(f"REJECT H1. Both endpoints reject; the difference favours the "
              f"{direction} kernel.")
    elif both:
        print("REJECT H1, but the two endpoints disagree in direction. "
              "Report as a discordant rejection, not an advantage.")
    else:
        print("DO NOT REJECT H1.")
        if confirmatory and mde:
            print(f"    Stated as an exclusion bound, not as 'no difference': an "
                  f"advantage larger than\n    {mde:.4f} in normAP is excluded at 80% "
                  f"power in this cell.")

    chosen_q = Counter(r["q_method"] for r in rows)
    chosen_c = Counter(r["c_method"] for r in rows)
    print(f"\n  inner-CV chose, across seeds:")
    print(f"    quantum   {dict(chosen_q.most_common())}")
    print(f"    classical {dict(chosen_c.most_common())}")
    print(f"  absolute level: quantum normAP {st.mean(r['q_normap'] for r in rows):.4f}, "
          f"classical {st.mean(r['c_normap'] for r in rows):.4f}")

    return {"dataset": dataset, "n_per_class": n_per_class, "cell": list(cell),
            "confirmatory": confirmatory, "normap": ap, "roc": roc,
            "reject": bool(both and agree),
            "quantum_chosen": dict(chosen_q), "classical_chosen": dict(chosen_c)}


def report_per_setting(dataset, q_by_cell, c_by_cell, cell, seeds):
    """Section 9: does the headline depend on the quantum side choosing?

    Returns the family as data. Until week 12 this returned None, so the only
    surviving trace of it was three rounded numbers per setting in a log:
    no n, no median, no sd, no confidence interval and no sensitivity t-test,
    because none of those is printed. The statistics are unchanged; what
    changes is that they are now readable without re-running this script.

    The Holm family size is computed rather than asserted. The previous header
    printed the literal "4", which was right for every run made so far and was
    never derived from the data.
    """
    attempted = sorted({r["setting"] for k, rs in q_by_cell.items() for r in rs})
    labels, tested, praw = [], [], []
    for setting in attempted:
        diffs = []
        for seed in seeds:
            k = (cell[0], cell[1], seed)
            qs, cs = q_by_cell.get(k), c_by_cell.get(k)
            if not qs or not cs:
                continue
            q = next((r for r in qs if r["setting"] == setting), None)
            if q is None:
                continue
            c = best_by_inner([r for r in cs if r["method"] in CLASSICAL_KERNELS])
            diffs.append(norm_ap(q) - norm_ap(c))
        if len(diffs) > 1:
            e = endpoint_test(diffs)
            labels.append(setting)
            tested.append(e)
            praw.append(e["p_wilcoxon"])
    family = {"family": "per_setting", "exploratory": True,
              "endpoint": "normap", "cell": list(cell),
              "holm_scope": "within this family only",
              "settings_attempted": attempted,
              "holm_family_size": len(labels),
              "settings_untested": [s for s in attempted if s not in labels],
              "levels": []}
    print(f"\n  EXPLORATORY: each quantum setting against best classical "
          f"(Holm-corrected within this family of {len(labels)})")
    if not labels:
        print("    no setting had more than one paired seed; nothing was tested")
        return family
    padj = holm(praw)
    for lab, e, pa in zip(labels, tested, padj):
        print(f"    {lab:<10} mean normAP {e['mean']:+.4f}   "
              f"p {fmt_p(e['p_wilcoxon'])}   Holm {fmt_p(pa)}")
        family["levels"].append({"setting": lab, **e, "p_holm": float(pa)})
    if family["settings_untested"]:
        print(f"    not tested (fewer than two paired seeds): "
              f"{', '.join(family['settings_untested'])}")
    return family


def report_sweep(dataset, q_by_cell, c_by_cell, seeds):
    """All 15 cells. Exploratory, Holm-corrected, and it decides nothing.

    Returns the family as data, for the same reason as `report_per_setting`.
    The header says "all cells"; a cell with fewer than two paired series is
    skipped, so the included and attempted counts are recorded and any gap is
    printed rather than left to be inferred from a shorter table.
    """
    print(f"\n  EXPLORATORY: all cells (Holm-corrected within this family; "
          f"no cell here bears on H1)")
    cells = sorted({(m, q) for (m, q, _) in q_by_cell})
    rows, praw = [], []
    for cell in cells:
        series = paired_series(q_by_cell, c_by_cell, cell, seeds)
        if len(series) < 2:
            continue
        e = endpoint_test([r["d_normap"] for r in series])
        rows.append((cell, e))
        praw.append(e["p_wilcoxon"])
    family = {"family": "all_cells", "exploratory": True, "endpoint": "normap",
              "holm_scope": "within this family only", "bears_on_h1": False,
              "cells_attempted": len(cells),
              "cells_included": len(rows),
              "cells_excluded": [list(c) for c in cells
                                 if c not in [r[0] for r in rows]],
              "holm_family_size": len(rows), "levels": []}
    if not rows:
        print("    no cell had two or more paired series; nothing was tested")
        return family
    adj = holm(praw)
    for (cell, e), pa in zip(rows, adj):
        family["levels"].append({"mapping": cell[0], "n_qubits": int(cell[1]),
                                 **e, "p_holm": float(pa)})
    print(f"    {'cell':<16}{'mean dNormAP':>14}{'p':>12}{'Holm':>12}")
    for (cell, e), pa in sorted(zip(rows, adj), key=lambda z: -z[0][1]["mean"]):
        star = "  *" if pa < ALPHA else ""
        print(f"    {cell[0] + '/' + str(cell[1]):<16}{e['mean']:>+14.4f}"
              f"{fmt_p(e['p_wilcoxon']):>12}{fmt_p(pa):>12}{star}")
    if family["cells_excluded"]:
        print(f"    {len(family['cells_excluded'])} of {len(cells)} cells not "
              f"tested (fewer than two paired series)")
    return family


# ------------------------------------------------------------------ main

def run(dataset, n_per_class, q_dir, c_dir, sweep, integrity_only=False, q_suffix=""):
    qpath = q_dir / f"{dataset}_matched_n{n_per_class}{q_suffix}.jsonl"
    cpath = c_dir / f"{dataset}_matched_n{n_per_class}.jsonl"
    qrecs, crecs = load(qpath), load(cpath)
    if qrecs is None or crecs is None:
        print(f"\nmissing: {qpath.name if qrecs is None else cpath.name}")
        return None, 1

    fatal, notes, q_by_cell, c_by_cell, is_arm = integrity(qrecs, crecs, dataset, n_per_class)
    print(f"\n--- {dataset}, {n_per_class} per class -------------------------------")
    for note in notes:
        print(f"  {note}")
    if fatal:
        print("\n  HALTED. Section 4 says a pairing failure aborts the analysis:")
        for f in fatal:
            print(f"    * {f}")
        return None, 2

    print("  integrity: clean. Pairing is sound on every cell.")
    if integrity_only:
        return None, 0

    seeds = sorted({r["seed"] for r in qrecs})
    cell = PRIMARY_CELL[dataset]
    # A post-hoc arm cannot be confirmatory. This is enforced from the RECORDS,
    # not from a flag, so no command line can mislabel it.
    confirmatory = (n_per_class == CONFIRMATORY_N) and not is_arm
    rows = paired_series(q_by_cell, c_by_cell, cell, seeds)
    summary = report_primary(dataset, n_per_class, rows, confirmatory)
    per_setting = report_per_setting(dataset, q_by_cell, c_by_cell, cell, seeds)
    all_cells = report_sweep(dataset, q_by_cell, c_by_cell, seeds) if sweep else None
    if summary is not None:
        # Additive only. Every field report_primary already returned is
        # untouched, so a regenerated file is comparable to its predecessor on
        # the keys that existed before.
        summary["seeds"] = [int(s) for s in seeds]
        summary["inputs"] = [file_provenance(qpath), file_provenance(cpath)]
        summary["exploratory_families"] = {
            "per_setting": per_setting,
            "all_cells": all_cells if sweep else "not requested (--sweep absent)"}
    return summary, 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=sorted(PRIMARY_CELL))
    ap.add_argument("--n-per-class", type=int, default=CONFIRMATORY_N)
    ap.add_argument("--all", action="store_true",
                    help="both datasets at 250 (confirmatory), then 100 and 50 as "
                         "the learning curve")
    ap.add_argument("--integrity-only", action="store_true",
                    help="check the sweep and print NO verdict. Use this first: it "
                         "answers 'is the run sound' without answering 'did it win', "
                         "so the two questions stay separable")
    ap.add_argument("--quantum-suffix", default="",
                    help="read a variant quantum file, e.g. _bw for the exploratory "
                         "bandwidth arm. The classical arm is never varied.")
    ap.add_argument("--sweep", action="store_true",
                    help="also print the 15-cell exploratory table")
    ap.add_argument("--quantum-dir", default=str(ROOT / "results" / "runs" / "quantum"))
    ap.add_argument("--classical-dir", default=str(ROOT / "results" / "runs" / "classical"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.out is None:
        args.out = str(ROOT / "results" / "analysis"
                       / f"primary_tests{args.quantum_suffix}.json")
    q_dir, c_dir = Path(args.quantum_dir), Path(args.classical_dir)

    print("H1: no quantum advantage in the pre-registered primary cell.")
    print("Rule: intersection-union, Wilcoxon signed-rank on 20 paired seeds, "
          "alpha 0.05 two-sided.")
    print("Selection of both arms is by inner-CV only. The confirmatory arm is "
          "250 per class.")
    if args.integrity_only:
        print("INTEGRITY ONLY: no hypothesis is tested and no verdict is printed.")

    jobs = []
    if args.all:
        jobs += [(d, 250) for d in sorted(PRIMARY_CELL)]
        jobs += [(d, n) for n in (100, 50) for d in sorted(PRIMARY_CELL)]
    else:
        if not args.dataset:
            ap.error("give --dataset or --all")
        jobs = [(args.dataset, args.n_per_class)]

    summaries, worst = [], 0
    for dataset, n in jobs:
        s, code = run(dataset, n, q_dir, c_dir, args.sweep, args.integrity_only,
                      args.quantum_suffix)
        worst = max(worst, code)
        if s:
            summaries.append(s)

    if summaries:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        meta = {
            "git_commit": git_commit(),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "script": "scripts/primary_tests.py",
            "is_new_run": True,
            "sweep_requested": bool(args.sweep),
            "note": ("This file is the output of a new run under the commit named "
                     "above. It does not authenticate any earlier printed or "
                     "logged figure, and an earlier figure that happens to match "
                     "is a match, not a verification. Each result names the input "
                     "files it read with their SHA-256 digests."),
        }
        out.write_text(json.dumps({"alpha": ALPHA, "rule": "intersection-union",
                                   "quantum_suffix": args.quantum_suffix,
                                   "confirmatory_n_per_class": CONFIRMATORY_N,
                                   "run": meta,
                                   "results": summaries}, indent=2, default=float) + "\n")
        print(f"\n-> {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")

    if worst == 2:
        print("\nOne or more arms halted on an integrity failure. No verdict stands.")
    sys.exit(worst)


if __name__ == "__main__":
    main()
