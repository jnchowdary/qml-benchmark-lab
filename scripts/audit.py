#!/usr/bin/env python3
"""One command that audits a quantum-classical comparison and says what it missed.

WHAT THIS IS FOR
----------------
Every check in this project was written because a specific reading went wrong,
and each one lives in its own script with its own CLI. That makes them useless
to anyone else, including to this project six months from now. This runs them
all against a results file and prints one line per check.

The audit is about METHOD, not about results. It never says whether a quantum
kernel won. It says whether the comparison was set up so that the answer would
mean anything, which is the question two published benchmarks in this area do
not appear to ask of themselves.

TWO TIERS, AND WHY THE DISTINCTION IS THE WHOLE DESIGN
-------------------------------------------------------
Tier 1 checks need only the result records, so they run against any pipeline
that can emit the schema below. Tier 2 checks need the Gram matrices or the
training data, so they cannot be portable and are reported as NOT RUN with the
reason. Pretending Tier 2 is portable would be the same class of error this
tool exists to catch: claiming a check happened when it could not have.

THE RECORD SCHEMA
-----------------
One JSON object per line. Nothing here is specific to quantum kernels; a record
is one model, scored once, on one train/test split.

  REQUIRED
    method                 str    what was fitted, e.g. "rbf" or "quantum-iqp-r1"
    seed                   int    identifies the split; records sharing a seed
                                  are assumed to share a train/test partition
    n_train, n_test        int
    test_base_rate         float  positive fraction in the test set
    test_average_precision float
    test_roc_auc           float

  STRONGLY RECOMMENDED (checks degrade to SKIP without them, and say so)
    test_label_fingerprint str    hash of the test labels IN ORDER. Without it
                                  no paired test can be verified, only assumed.
    shuffled               bool   marks a permuted-label control record
    final_converged        bool   false if the solver hit its iteration cap
    cell                   dict   any configuration that groups records, e.g.
                                  {"mapping": "pca", "n_qubits": 12}. Used as
                                  the UNIT OF ANALYSIS: seeds inside one cell
                                  are repeats, not independent observations.

  OPTIONAL
    inner_score            float  selection score, for the selection check
    edge                   dict   hyperparameters sitting on a grid boundary

Records with extra fields are fine and are ignored.

EXIT CODES
----------
0 all checks passed or were skipped; 1 at least one warning; 2 at least one
failure. A failure means a conclusion drawn from this file is not supported by
the file, not that the conclusion is wrong.

Usage:
    PYTHONPATH=src python scripts/audit.py results/runs/quantum/churn_matched_n250.jsonl
    PYTHONPATH=src python scripts/audit.py RESULTS.jsonl --control RESULTS_shuffled.jsonl
    PYTHONPATH=src python scripts/audit.py RESULTS.jsonl --json report.json
"""

from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from qbench.metrics import chance_average_precision  # noqa: E402

PASS, WARN, FAIL, SKIP, NOT_RUN = "PASS", "WARN", "FAIL", "SKIP", "NOT RUN"
ALPHA = 0.05

# docs/deviations.md D2: kernels at cond 1e16 to 1e19 give a reproducibility
# floor near this in average precision. Overridable, because it is a property of
# the pipeline being audited and not a universal constant.
DEFAULT_PRECISION_FLOOR = 1e-3


@dataclass
class Outcome:
    name: str
    status: str
    detail: str
    tier: int = 1
    numbers: dict = field(default_factory=dict)


def load(path):
    return [json.loads(l) for l in Path(path).open() if l.strip()]


def has(recs, field_name):
    return bool(recs) and all(field_name in r for r in recs)


def norm_ap(r):
    n, p = int(r["n_test"]), int(round(float(r["test_base_rate"]) * int(r["n_test"])))
    c = chance_average_precision(n, p)
    return (float(r["test_average_precision"]) - c) / (1 - c) if c < 1 else float("nan")


# Fields that are never configuration: they identify a record or describe its
# outcome, so grouping by them would put every record in its own cell.
NEVER_CELL = {
    # identity and outcome
    "method", "seed", "inner_score", "shuffled", "final_converged",
    "final_fallback_rank", "params", "C", "edge", "grid_scores", "cell",
    # provenance
    "git_commit", "device", "c_grid", "n_seeds",
    # cost telemetry: varies per record and is not a configuration. Without
    # this, a field like circuit_evaluations taking two values, each scored by
    # every method, would be inferred as a configuration and silently double
    # the cell count.
    "circuit_evaluations", "simulator_executions", "cache_hits",
    # hyperparameters SELECTED per record rather than fixed per configuration
    "bandwidth", "bandwidth_grid", "setting",
}


def infer_cell_fields(recs):
    """Work out which fields define a configuration, from the data.

    The first version of this tool required a nested `cell` dict and fell back
    to a single cell when it was absent. Run against this project's OWN results,
    where mapping and n_qubits are top-level fields, it collapsed fifteen
    configurations into one: it skipped the unit-of-analysis check that exists
    for exactly that case, understated the multiplicity correction fifteenfold,
    and pooled between-cell variance into the paired sd, reporting a minimum
    detectable effect five times too large.

    A configuration field is one that varies across records but NOT across the
    methods being compared: every one of its values is scored by the same set of
    methods. That is what makes records with different values of it separate
    comparisons rather than separate arms of one comparison. The rule needs no
    knowledge of any particular pipeline.

    The inferred grouping is always printed, because a wrong guess here quietly
    changes three other answers and the reader has to be able to see it.
    """
    methods = {r.get("method") for r in recs}
    if len(methods) < 2:
        return []
    candidates = []
    common = set(recs[0]) if recs else set()
    for r in recs:
        common &= set(r)
    for f in sorted(common):
        if f in NEVER_CELL or f.startswith("test_") or f.startswith("n_test"):
            continue
        vals = {r[f] for r in recs if isinstance(r[f], (str, int, float, bool))}
        if not 2 <= len(vals) <= max(2, len(recs) // 2):
            continue
        # every value of a configuration field is scored by the same methods
        by_val = defaultdict(set)
        for r in recs:
            by_val[r[f]].add(r.get("method"))
        if all(m == methods for m in by_val.values()):
            candidates.append(f)
    return candidates


def cell_of(r, fields=None):
    """The configuration a record belongs to. Records sharing a cell and a seed
    are one split scored by different methods, which is what makes them pairable.

    Falling back to the method would be worse than useless: it would put each
    method in its own configuration, so nothing would ever pair.
    """
    if fields:
        return tuple((f, str(r.get(f))) for f in fields)
    c = r.get("cell")
    if isinstance(c, dict) and c:
        return tuple(sorted((k, str(v)) for k, v in c.items()))
    return (("cell", "unspecified"),)


# ----------------------------------------------------------------- tier 1

def check_schema(recs, ctx):
    need = ("method", "seed", "n_train", "n_test", "test_base_rate",
            "test_average_precision", "test_roc_auc")
    missing = [f for f in need if not has(recs, f)]
    if missing:
        return Outcome("schema", FAIL,
                       f"required fields missing from some records: {', '.join(missing)}. "
                       f"Nothing below can be trusted.")
    opt = [f for f in ("test_label_fingerprint", "shuffled", "final_converged", "cell")
           if not has(recs, f)]
    if opt:
        return Outcome("schema", WARN,
                       f"{len(recs)} records readable; missing recommended fields "
                       f"{', '.join(opt)}, so some checks below will skip.")
    return Outcome("schema", PASS, f"{len(recs)} records, all required and "
                                   f"recommended fields present.")


def check_chance_correction(recs, ctx):
    """A random ranker's average precision exceeds the base rate at finite n.

    Comparing raw AP across test sets of different sizes therefore compares two
    different null levels. This is the error that made a clean pipeline look
    like a 2.2-sigma leak in this project's week 3.
    """
    sizes = sorted({(int(r["n_test"]),
                     int(round(float(r["test_base_rate"]) * int(r["n_test"]))))
                    for r in recs})
    chances = {s: chance_average_precision(*s) for s in sizes}
    spread = max(chances.values()) - min(chances.values())
    worst = max(chances.items(), key=lambda kv: kv[1] - kv[0][1] / kv[0][0])
    (n, p), c = worst
    excess = c - p / n
    if spread > 1e-6:
        return Outcome("chance correction", WARN,
                       f"test sets of {len(sizes)} different shapes here, with chance AP "
                       f"from {min(chances.values()):.4f} to {max(chances.values()):.4f}. "
                       f"Raw AP is not comparable across them; normalise against exact "
                       f"chance, not the base rate.",
                       numbers={"chance_spread": spread})
    return Outcome("chance correction", PASS,
                   f"one test-set shape (n={n}, p={p}); chance AP is {c:.4f}, which "
                   f"exceeds the base rate {p / n:.4f} by {excess:.4f}. Constant here, "
                   f"so raw AP is comparable WITHIN this file and nowhere else.",
                   numbers={"chance_ap": c, "base_rate": p / n})


def check_negative_control(recs, ctx):
    ctrl = ctx.get("control")
    if not ctrl:
        return Outcome("negative control", SKIP,
                       "no permuted-label control supplied (--control). Without one "
                       "there is no evidence the pipeline does not leak.")
    roc = [float(r["test_roc_auc"]) for r in ctrl]
    nap = [norm_ap(r) for r in ctrl]
    floor = ctx["floor"]
    out, bad = {}, []
    for label, vals, null in (("ROC-AUC", roc, 0.5), ("normAP", nap, 0.0)):
        m, se = float(np.mean(vals)), float(np.std(vals, ddof=1) / math.sqrt(len(vals)))
        z = (m - null) / se if se > 0 else 0.0
        out[label] = {"mean": m, "sigma": z, "se": se}
        # BOTH conditions, never the sigma alone. A control whose records are
        # near-identical has a standard error of order 1e-22, which is floating
        # point residue rather than a measured spread, and dividing by it turned
        # a deviation of 0.000014 into 3.5e16 sigma when this check was first
        # written. A deviation below the pipeline's own reproducibility floor is
        # not a leak however many sigma the arithmetic produces.
        if abs(z) > 2 and abs(m - null) > floor:
            bad.append(f"{label} {m:.4f} ({z:+.2f} sigma from {null})")
    if bad:
        return Outcome("negative control", FAIL,
                       f"control deviates from its null by more than the {floor:g} "
                       f"floor: {'; '.join(bad)}. Investigate before reading any result "
                       f"in the main file.", numbers=out)
    return Outcome("negative control", PASS,
                   f"{len(ctrl)} control records: ROC-AUC {out['ROC-AUC']['mean']:.4f} "
                   f"({out['ROC-AUC']['sigma']:+.2f} sigma), normAP "
                   f"{out['normAP']['mean']:+.4f} ({out['normAP']['sigma']:+.2f} sigma).",
                   numbers=out)


def check_pairing(recs, ctx):
    if not has(recs, "test_label_fingerprint"):
        return Outcome("pairing integrity", SKIP,
                       "no test_label_fingerprint. Paired tests across methods cannot "
                       "be verified, only assumed, and a silent mismatch is invisible.")
    groups = defaultdict(set)
    for r in recs:
        groups[(r["seed"], cell_of(r, ctx["cell_fields"]))].add(r["test_label_fingerprint"])
    bad = [k for k, v in groups.items() if len(v) > 1]
    if bad:
        return Outcome("pairing integrity", FAIL,
                       f"{len(bad)} (seed, cell) groups contain records scored on "
                       f"DIFFERENT test points, e.g. seed {bad[0][0]}. Any paired "
                       f"statistic over them is meaningless.")
    return Outcome("pairing integrity", PASS,
                   f"all {len(groups)} (seed, cell) groups share one test-label "
                   f"fingerprint, so paired tests over them are valid.")


def check_convergence(recs, ctx):
    if not has(recs, "final_converged"):
        return Outcome("solver health", SKIP, "no final_converged field.")
    bad = [r for r in recs if not r["final_converged"]]
    if bad:
        return Outcome("solver health", FAIL,
                       f"{len(bad)} of {len(recs)} records were scored from a model that "
                       f"hit its iteration cap. A non-converged fit is not a result.")
    return Outcome("solver health", PASS, f"all {len(recs)} final fits converged.")


def check_unit_of_analysis(recs, ctx):
    """Seeds inside a cell are repeats of one configuration, not independent
    observations of a trend across configurations.

    Treating 300 records as 300 independent points instead of 15 cells is how a
    column of sub-precision-floor noise became p = 0.0099 in this project's own
    week 4. The check cannot see which tests a reader will run, so it reports
    the two sample sizes and lets the reader be explicit about which is theirs.
    """
    cells = {cell_of(r, ctx["cell_fields"]) for r in recs}
    seeds = {r["seed"] for r in recs}
    if len(cells) < 2:
        return Outcome("unit of analysis", SKIP,
                       "records carry no 'cell' field or only one configuration, so "
                       "independent units cannot be identified.")
    return Outcome("unit of analysis", WARN,
                   f"{len(recs)} records = {len(cells)} configurations x ~{len(seeds)} "
                   f"seeds. Across-configuration claims have n={len(cells)}, not "
                   f"n={len(recs)}. State which n any reported p-value rests on.",
                   numbers={"n_cells": len(cells), "n_seeds": len(seeds),
                            "n_records": len(recs)})


def check_power(recs, ctx):
    """Smallest paired difference this file could resolve at 80% power."""
    by_cell = defaultdict(lambda: defaultdict(dict))
    for r in recs:
        by_cell[cell_of(r, ctx["cell_fields"])][r["seed"]][r["method"]] = norm_ap(r)
    sds = []
    for cell, by_seed in by_cell.items():
        methods = sorted({m for v in by_seed.values() for m in v})
        for i, a in enumerate(methods):
            for b in methods[i + 1:]:
                d = [v[a] - v[b] for v in by_seed.values() if a in v and b in v]
                if len(d) > 1:
                    sds.append(st.stdev(d))
    if not sds:
        return Outcome("statistical power", SKIP,
                       "fewer than two methods per seed, so no paired difference exists.")
    sd = float(np.median(sds))
    n = int(np.median([len(v) for v in by_cell.values()]))
    if n < 2:
        return Outcome("statistical power", SKIP, "too few seeds per configuration.")
    crit = stats.t.ppf(1 - ALPHA / 2, n - 1)
    mde = float(sd / math.sqrt(n) * (crit + stats.t.ppf(0.80, n - 1)))
    status = WARN if mde > 0.02 else PASS
    return Outcome("statistical power", status,
                   f"median paired sd {sd:.4f} over {n} seeds gives a minimum detectable "
                   f"effect near {mde:.4f} in normAP. A null result here excludes effects "
                   f"LARGER than that and nothing smaller."
                   + (" That is coarse relative to effects this literature reports."
                      if status == WARN else ""),
                   numbers={"paired_sd": sd, "n_seeds": n, "mde": mde})


def check_precision_floor(recs, ctx):
    floor = ctx["floor"]
    by_cell = defaultdict(lambda: defaultdict(dict))
    for r in recs:
        by_cell[cell_of(r, ctx["cell_fields"])][r["seed"]][r["method"]] = norm_ap(r)
    small = tot = 0
    for by_seed in by_cell.values():
        methods = sorted({m for v in by_seed.values() for m in v})
        for i, a in enumerate(methods):
            for b in methods[i + 1:]:
                d = [v[a] - v[b] for v in by_seed.values() if a in v and b in v]
                if d:
                    tot += 1
                    small += abs(float(np.mean(d))) < floor
    if not tot:
        return Outcome("precision floor", SKIP, "no paired comparisons to measure.")
    if small:
        return Outcome("precision floor", WARN,
                       f"{small} of {tot} method pairs differ by less than the declared "
                       f"floor of {floor:g}. Below it a difference is not reproducible "
                       f"and must be reported as such, not as a measurement.",
                       numbers={"below_floor": small, "pairs": tot, "floor": floor})
    return Outcome("precision floor", PASS,
                   f"all {tot} method-pair differences exceed the declared floor "
                   f"of {floor:g}.")


def check_multiplicity(recs, ctx):
    by_cell = defaultdict(set)
    for r in recs:
        by_cell[cell_of(r, ctx["cell_fields"])].add(r["method"])
    comparisons = sum(len(m) * (len(m) - 1) // 2 for m in by_cell.values())
    if comparisons <= 1:
        return Outcome("multiplicity", PASS, f"{comparisons} comparison in this file.")
    bonf = ALPHA / comparisons
    return Outcome("multiplicity", WARN,
                   f"this file supports {comparisons} pairwise comparisons across "
                   f"{len(by_cell)} configurations. Uncorrected, the chance of at least "
                   f"one spurious rejection at alpha {ALPHA} is about "
                   f"{1 - (1 - ALPHA) ** comparisons:.2f}. Declare which are "
                   f"confirmatory, or correct (Bonferroni would be {bonf:.2e}).",
                   numbers={"comparisons": comparisons, "bonferroni": bonf})


def check_cross_arm(recs, ctx):
    """The comparison that is actually being made usually spans two files.

    Handed one arm, every power and multiplicity figure above describes
    comparisons WITHIN that arm. This project's own quantum file gave a minimum
    detectable effect of 0.0555 measured between quantum settings, against the
    0.0171 its power analysis had measured for the quantum-versus-classical
    comparison that the hypothesis actually tests. Both numbers were right about
    different pairs, and reporting only the first would have described the power
    of a comparison nobody is making.
    """
    other = ctx.get("compare")
    if not other:
        return Outcome("cross-arm comparison", SKIP,
                       "only one arm supplied. Every figure above describes "
                       "comparisons WITHIN this file. If the claim being made is "
                       "against another arm, pass it with --compare or the power and "
                       "multiplicity numbers describe the wrong comparison.")
    fields = ctx["cell_fields"]
    a, b = defaultdict(dict), defaultdict(dict)
    for r in recs:
        a[(r["seed"], cell_of(r, fields))][r["method"]] = r
    for r in other:
        b[(r["seed"], cell_of(r, ctx["compare_fields"]))][r["method"]] = r

    keys = sorted(set(a) & set(b), key=str)
    if not keys:
        return Outcome("cross-arm comparison", FAIL,
                       "no (seed, configuration) group appears in both files, so the "
                       "two arms cannot be paired at all. Check that both were run on "
                       "the same splits and configurations.")

    mismatched, unverifiable = [], 0
    for k in keys:
        fps = {r.get("test_label_fingerprint") for r in list(a[k].values()) + list(b[k].values())}
        if None in fps:
            unverifiable += 1
        fps.discard(None)
        if len(fps) > 1:
            mismatched.append(k)
    if mismatched:
        return Outcome("cross-arm comparison", FAIL,
                       f"{len(mismatched)} of {len(keys)} paired groups were scored on "
                       f"DIFFERENT test points across the two files, e.g. seed "
                       f"{mismatched[0][0]}. The arms are not comparable.")

    # Keyed by (configuration, method pair), NOT by method pair alone. Pooling
    # every configuration into one bucket makes n the record count rather than
    # the seed count: the first version of this check reported n = 300 on 20
    # seeds and a minimum detectable effect of 0.0009. That is the fourth
    # instance in this project of the same mistake, committed inside the check
    # written to explain it, which is the clearest possible argument for the
    # unit-of-analysis warning being in the report at all.
    diffs = defaultdict(list)
    for (seed, cell) in keys:
        k = (seed, cell)
        for ma, ra in a[k].items():
            for mb, rb in b[k].items():
                diffs[(cell, ma, mb)].append(norm_ap(ra) - norm_ap(rb))
    sds = [st.stdev(v) for v in diffs.values() if len(v) > 1]
    n = int(np.median([len(v) for v in diffs.values()]))
    if not sds or n < 2:
        return Outcome("cross-arm comparison", WARN,
                       f"{len(keys)} groups pair across the two files, but too few "
                       f"seeds per pair to estimate power.")
    sd = float(np.median(sds))
    crit = stats.t.ppf(1 - ALPHA / 2, n - 1)
    mde = float(sd / math.sqrt(n) * (crit + stats.t.ppf(0.80, n - 1)))
    # Never claim a verification that did not happen. Without fingerprints the
    # arms are ASSUMED to share their test points; saying otherwise would be the
    # failure this whole tool exists to catch.
    if unverifiable:
        verdict, pairing = WARN, (f"{len(keys)} groups pair across the two files by "
                                  f"(seed, configuration), but {unverifiable} of them "
                                  f"carry no test_label_fingerprint, so matching test "
                                  f"points are ASSUMED and not verified.")
    else:
        verdict, pairing = PASS, (f"{len(keys)} (seed, configuration) groups pair "
                                  f"across the two files on verified matching test "
                                  f"points.")
    return Outcome("cross-arm comparison", verdict,
                   f"{pairing} Across-arm paired sd {sd:.4f} over "
                   f"{n} seeds per configuration gives a minimum detectable effect "
                   f"near {mde:.4f}. THIS "
                   f"is the power of the comparison being made; the figure above is "
                   f"the power of comparisons within one arm.",
                   numbers={"paired_groups": len(keys), "cross_arm_sd": sd,
                            "cross_arm_mde": mde, "n_seeds": n,
                            "method_pairs": len(diffs)})


def check_selection_leak(recs, ctx):
    """Selection must be on an inner score, never on the reported test score."""
    if not has(recs, "inner_score"):
        return Outcome("selection", SKIP,
                       "no inner_score field, so it cannot be shown that model "
                       "selection used training folds rather than the test score.")
    rho = stats.spearmanr([float(r["inner_score"]) for r in recs],
                          [norm_ap(r) for r in recs])
    return Outcome("selection", PASS,
                   f"inner scores recorded alongside test scores; their rank "
                   f"correlation is {rho.statistic:+.3f}. Selection auditable.",
                   numbers={"spearman_inner_vs_test": float(rho.statistic)})


# ----------------------------------------------------------------- tier 2

TIER2 = [
    ("kernel conditioning", "needs the Gram matrices. An ill-conditioned kernel makes "
     "the SVM dual underdetermined, so decision scores move at machine precision and "
     "any threshold-based test (McNemar) is invalid."),
    ("classical surrogate equivalence", "needs the kernels and training data. Fits the "
     "nearest classical kernel and runs it through the same pipeline; a quantum kernel "
     "that scores what its surrogate scores is that surrogate."),
    ("grid adequacy against a shuffled null", "needs a re-run on permuted labels with a "
     "widened grid. Widening raises the best inner score even when nothing is better, "
     "so edge flags alone never justify it."),
    ("bandwidth tuning", "needs the embedding. A fidelity kernel with a fixed data "
     "scale is not a tuned model; the classical side almost always gets a bandwidth "
     "grid and the quantum side almost never does."),
]

CHECKS = [check_schema, check_chance_correction, check_negative_control, check_pairing,
          check_convergence, check_unit_of_analysis, check_power,
          check_precision_floor, check_multiplicity, check_cross_arm,
          check_selection_leak]


def run(path, control, floor, cell_fields=None, compare=None):
    recs = load(path)
    if not recs:
        print(f"{path}: empty")
        return 2, []
    fields = cell_fields if cell_fields is not None else infer_cell_fields(recs)
    other = load(compare) if compare else None
    ctx = {"control": load(control) if control else None, "floor": floor,
           "cell_fields": fields, "compare": other,
           "compare_fields": (cell_fields if cell_fields is not None
                              else infer_cell_fields(other)) if other else None}
    outs = []
    for fn in CHECKS:
        try:
            outs.append(fn(recs, ctx))
        except Exception as exc:                      # a broken check is a failure
            outs.append(Outcome(fn.__name__, FAIL, f"check raised {exc!r}"))
    return fields, outs


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("results")
    ap.add_argument("--control", help="permuted-label companion file")
    ap.add_argument("--floor", type=float, default=DEFAULT_PRECISION_FLOOR,
                    help="reproducibility floor of the pipeline, in normAP")
    ap.add_argument("--cell-fields", nargs="*", default=None,
                    help="fields that define a configuration, e.g. mapping n_qubits. "
                         "Inferred from the data when omitted; the inference is always "
                         "printed because a wrong grouping silently changes three "
                         "other answers.")
    ap.add_argument("--compare",
                    help="the other arm of the comparison, e.g. the classical results. "
                         "Without it every figure describes comparisons WITHIN one arm.")
    ap.add_argument("--json", help="write the report here")
    args = ap.parse_args()

    fields, outs = run(args.results, args.control, args.floor, args.cell_fields,
                       args.compare)

    print(f"\nAUDIT: {args.results}")
    print("This audits METHOD, not results. It never says which model won.")
    if fields:
        print(f"  Configuration grouped by: {', '.join(fields)}"
              f"{' (given)' if args.cell_fields else ' (inferred from the data)'}. "
              f"Override with --cell-fields if that is wrong.")
    else:
        print("  No configuration fields found, so every record is treated as one "
              "cell. Pass --cell-fields if this file has configurations.")
    print()
    width = max(len(o.name) for o in outs)
    for o in outs:
        print(f"  [{o.status:^7}] {o.name:<{width}}  {o.detail}")

    print(f"\n  Not runnable from records alone:")
    for name, why in TIER2:
        print(f"  [{NOT_RUN:^7}] {name}")
        print(f"            {why}")

    counts = {s: sum(o.status == s for o in outs) for s in (PASS, WARN, FAIL, SKIP)}
    print(f"\n  {counts[PASS]} passed, {counts[WARN]} warnings, {counts[FAIL]} failed, "
          f"{counts[SKIP]} skipped for missing fields.")
    if counts[FAIL]:
        print("  A FAIL means a conclusion drawn from this file is not supported BY "
              "this file. It does not mean the conclusion is wrong.")

    if args.json:
        p = Path(args.json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(
            {"file": args.results, "control": args.control, "floor": args.floor,
             "checks": [vars(o) for o in outs],
             "not_runnable": [{"name": n, "reason": w} for n, w in TIER2]},
            indent=2, default=float) + "\n")
        print(f"\n-> {p}")

    sys.exit(2 if counts[FAIL] else (1 if counts[WARN] else 0))


if __name__ == "__main__":
    main()
