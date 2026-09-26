#!/usr/bin/env python3
"""Regenerate D6's power table from the audit, across every arm, in one run.

WHY THIS EXISTS RATHER THAN A HAND-BUILT TABLE
-----------------------------------------------
D6's table is the most citable thing in this project: it is the record that
every row of the registered power analysis is understated by 2.3x to 3.9x. It
was assembled by reading numbers out of audit output and typing them into a
markdown table. Two things make that unacceptable now.

First, this project has already destroyed results by hand-transcribing them: a
filename collision overwrote two of three all-cells runs, and scoring then meant
copying sixty rows out of a log. Second, the audit that produced those numbers
had four defects in its checks, found on 26 September by reading a report on
real records rather than by any test. One of them silently discarded two thirds
of a comparison file and reported a plausible minimum detectable effect computed
from the survivors. A table built by hand from a tool with that defect cannot be
patched a row at a time; it has to be regenerated and the rows compared.

So this script computes every row, prints them next to whatever D6 currently
claims, and writes the JSON. A row that does not reproduce is a finding.

THREE QUANTITIES, NEVER MIXED
-----------------------------
D6's first correction was itself corrected for mixing two of them, so all three
are computed separately and labelled:

  arm level     median over every configuration and method pair in the file,
                which is what a claim about "the churn 250 arm" rests on
  primary cell  median over every method pair inside the pre-registered cell
  H1 pair       the variance of the comparison H1 ACTUALLY makes: best quantum
                against best classical, each selected per seed by inner score,
                paired across seeds

The third is the one an exclusion bound on the primary test needs, and it is not
a median over anything. A bound saying "an advantage larger than X is excluded"
is a statement about the pair the test forms, so it must be measured on that
pair. Quoting a median over all method pairs instead silently substitutes the
variance of comparisons nobody made -- which is D6's own error, one level down.

Usage:
    PYTHONPATH=src python scripts/audit_sweep.py
    PYTHONPATH=src python scripts/audit_sweep.py --json results/audits/d6_table.json
"""

from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import audit  # noqa: E402
from primary_tests import PRIMARY_CELL, best_by_inner  # noqa: E402

RUNS = ROOT / "results" / "runs"
# Both pipelines write these as top-level fields, so the grouping is stated
# rather than inferred. Inference intersects to nothing when one arm covers a
# single configuration and the other covers fifteen, which is the defect that
# made this rebuild necessary in the first place.
CELL_FIELDS = ["mapping", "n_qubits"]

# What docs/deviations.md D6 claims today, split by WHICH quantity each of its
# two tables holds. Getting this mapping wrong is how the first version of this
# script reported the bandwidth row as not reproducing: it compared D6's H1-pair
# figure against a median over every method pair in the cell, which is a
# different number about a different comparison. D6 was right; the checker was
# asking it the wrong question.
D6_ARM = {                      # D6's main table: "every row of section 5"
    ("churn", 250, "registered"): 0.0608,
    ("churn", 100, "registered"): 0.1005,
    ("churn", 50, "registered"): 0.1368,
    ("fraud", 250, "registered"): 0.0138,
    ("fraud", 100, "registered"): 0.0365,
    ("fraud", 50, "registered"): 0.0571,
}
D6_H1 = {                       # D6's second table: the exclusion-bound quantity
    ("churn", 250, "registered"): 0.0608,
    ("fraud", 250, "registered"): 0.0063,
    ("churn", 250, "bandwidth"): 0.0233,
}
# churn 250 appears in both at 0.0608. That is the coincidence D6's own
# correction note records, and it is what made an arm-level figure and an
# H1-pair figure indistinguishable on inspection.


def arms():
    for dataset in ("churn", "fraud"):
        for n in (250, 100, 50):
            q = RUNS / "quantum" / f"{dataset}_matched_n{n}.jsonl"
            c = RUNS / "classical" / f"{dataset}_matched_n{n}.jsonl"
            if q.exists() and c.exists():
                yield dataset, n, "registered", q, c
        q = RUNS / "quantum" / f"{dataset}_matched_n250_bw.jsonl"
        c = RUNS / "classical" / f"{dataset}_matched_n250.jsonl"
        if q.exists() and c.exists():
            yield dataset, 250, "bandwidth", q, c


def in_primary(recs, dataset):
    mapping, nq = PRIMARY_CELL[dataset]
    return [r for r in recs
            if r.get("mapping") == mapping and int(r.get("n_qubits", -1)) == nq]


def measure_h1(q_recs, c_recs):
    """Paired sd and MDE of best-quantum vs best-classical, by the registered rule."""
    qs, cs = defaultdict(list), defaultdict(list)
    for r in q_recs:
        qs[r["seed"]].append(r)
    for r in c_recs:
        cs[r["seed"]].append(r)
    diffs = []
    for seed in sorted(set(qs) & set(cs), key=str):
        pool = qs[seed] + cs[seed]
        if not all("inner_score" in r for r in pool):
            return None, None, None, "no inner_score, so the selection cannot be redone"
        a, b = best_by_inner(qs[seed]), best_by_inner(cs[seed])
        fa, fb = a.get("test_label_fingerprint"), b.get("test_label_fingerprint")
        if fa and fb and fa != fb:
            return None, None, None, f"seed {seed} scored on different test points"
        diffs.append(audit.norm_ap(a) - audit.norm_ap(b))
    if len(diffs) < 2:
        return None, None, None, "fewer than two shared seeds"
    n = len(diffs)
    sd = st.stdev(diffs)
    crit = stats.t.ppf(1 - audit.ALPHA / 2, n - 1)
    mde = sd / math.sqrt(n) * (crit + stats.t.ppf(0.80, n - 1))
    return sd, mde, float(st.fmean(diffs)), ""


def measure(q_recs, c_recs):
    """Cross-arm paired sd and MDE, or the reason there is none."""
    ctx = {"compare": c_recs, "cell_fields": CELL_FIELDS,
           "compare_fields": CELL_FIELDS, "floor": audit.DEFAULT_PRECISION_FLOOR,
           "control": None, "hook": None, "hook_sample": 0}
    o = audit.check_cross_arm(q_recs, ctx)
    if o.status == audit.FAIL or "cross_arm_mde" not in (o.numbers or {}):
        return None, None, o.status, o.detail
    return o.numbers["cross_arm_sd"], o.numbers["cross_arm_mde"], o.status, ""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", help="write the rebuilt table here")
    args = ap.parse_args()

    rows, mismatches = [], []
    for dataset, n, arm, qp, cp in arms():
        q, c = audit.load(str(qp)), audit.load(str(cp))
        a_sd, a_mde, a_st, a_why = measure(q, c)
        pq, pc = in_primary(q, dataset), in_primary(c, dataset)
        p_sd, p_mde, p_st, p_why = measure(pq, pc)
        h_sd, h_mde, h_obs, h_why = measure_h1(pq, pc)
        key = (dataset, n, arm)
        row = {"dataset": dataset, "n_per_class": n, "arm": arm,
               "arm_sd": a_sd, "arm_mde": a_mde, "arm_status": a_st,
               "primary_sd": p_sd, "primary_mde": p_mde, "primary_status": p_st,
               "h1_sd": h_sd, "h1_mde": h_mde, "h1_observed": h_obs,
               "d6_arm_claim": D6_ARM.get(key), "d6_h1_claim": D6_H1.get(key),
               "note": a_why or p_why or h_why,
               "resolvable": (None if (h_obs is None or h_mde is None)
                              else abs(h_obs) > h_mde)}
        for label, claim, got in (("arm", D6_ARM.get(key), a_mde),
                                  ("H1 pair", D6_H1.get(key), h_mde)):
            if claim is None:
                continue
            if got is None or abs(got - claim) > 5e-4:
                row["reproduces"] = False
                mismatches.append((dataset, n, arm, label, claim, got))
            else:
                row.setdefault("reproduces", True)
        rows.append(row)

    print("\nD6 POWER TABLE, REBUILT")
    print(f"  grouping stated as {CELL_FIELDS}, never inferred")
    print(f"  {'arm':<26} {'arm sd -> MDE':>20} {'primary sd -> MDE':>22} "
          f"{'H1 pair sd -> MDE':>22} {'H1 obs':>9} {'D6 arm/H1':>15}")
    for r in rows:
        name = f"{r['dataset']} {r['n_per_class']} {r['arm']}"
        a = (f"{r['arm_sd']:.4f} -> {r['arm_mde']:.4f}"
             if r["arm_mde"] is not None else f"[{r['arm_status']}]")
        p = (f"{r['primary_sd']:.4f} -> {r['primary_mde']:.4f}"
             if r["primary_mde"] is not None else f"[{r['primary_status']}]")
        h = (f"{r['h1_sd']:.4f} -> {r['h1_mde']:.4f}"
             if r["h1_mde"] is not None else "[none]")
        ob = f"{r['h1_observed']:+.4f}" if r["h1_observed"] is not None else "-"
        d = "/".join(f"{v:.4f}" for v in (r["d6_arm_claim"], r["d6_h1_claim"])
                     if v is not None) or "-"
        res = "" if r["resolvable"] is None else ("  RESOLVABLE" if r["resolvable"]
                                                 else "  below MDE")
        flag = "" if r.get("reproduces", True) else "   <- DOES NOT REPRODUCE"
        print(f"  {name:<26} {a:>20} {p:>22} {h:>22} {ob:>9} {d:>15}{res}{flag}")

    if mismatches:
        print(f"\n  {len(mismatches)} row(s) do not reproduce:")
        for dataset, n, arm, label, claim, got in mismatches:
            g = f"{got:.4f} ({got / claim:.2f}x)" if got is not None else "not measurable"
            print(f"    {dataset} {n} {arm} [{label}]: D6 says {claim:.4f}, "
                  f"measured {g}")
        print("  D6 is a frozen record. Correct it by appending, never by editing "
              "the figure in place.")
    else:
        print("\n  Every row D6 claims reproduces from the fixed audit.")

    print("\n  An exclusion bound on the primary test quotes the H1 PAIR column.")
    print("  A claim about a whole arm quotes the arm column. They are different")
    print("  quantities and this project has already conflated two of them twice.")
    n_res = sum(1 for r in rows if r["resolvable"])
    print(f"\n  {n_res} of {len(rows)} arms show an observed difference LARGER than "
          f"that arm's own\n  minimum detectable effect. In the rest the observed "
          f"value is smaller than the\n  resolution of the comparison that produced "
          f"it, which is not evidence of\n  equivalence and is not a measurement of "
          f"a small effect.")

    if args.json:
        p = Path(args.json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"cell_fields": CELL_FIELDS, "rows": rows},
                                indent=2, default=float) + "\n")
        print(f"\n-> {p}")
    sys.exit(1 if mismatches else 0)


if __name__ == "__main__":
    main()
