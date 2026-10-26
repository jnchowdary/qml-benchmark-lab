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
from itertools import zip_longest
import statistics as st
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy import stats

# EXTRACTED from scripts/audit.py of the QML Benchmark Lab research repository.
# This is the ONLY edit made to that file: the two statistics functions were
# imported from the `qbench` research package there, and here they live in
# byte-identical copies of their source modules. Nothing else is changed, so a
# divergence in any answer is a finding rather than a port. See EXTRACTION.md.
from ._qbench_stats import rank_correlation  # noqa: E402
from ._qbench_metrics import chance_average_precision  # noqa: E402
from . import provenance as prov  # noqa: E402
from . import __version__  # noqa: E402

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
    "n_nonconverged", "n_failed", "elapsed_s", "wall_clock_s",
    # hyperparameters SELECTED per record rather than fixed per configuration
    "bandwidth", "bandwidth_grid", "setting",
} | prov.NEVER_CELL_ADDITIONS


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
        by_val = defaultdict(set)
        counts = defaultdict(int)
        for r in recs:
            by_val[r[f]].add(r.get("method"))
            counts[r[f]] += 1
        # Every value of a configuration field is scored by the same methods.
        if not all(m == methods for m in by_val.values()):
            continue
        # And a configuration is a DESIGNED grid, so its values appear in
        # roughly equal numbers. Telemetry does not: on churn at 100 per class
        # the field n_nonconverged varied, was scored by every method, and so
        # passed the rule above, giving 20 configurations instead of 15, ragged
        # 367-group pairing, and a cross-arm failure because the other arm
        # inferred a different field set. Its values were wildly unbalanced,
        # which is what distinguishes an outcome from a design.
        if max(counts.values()) > 3 * min(counts.values()):
            continue
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
    # This failure used to end "Nothing below can be trusted." On the first
    # foreign audit -- the Kakavand hardware deposit, whose endpoint is balanced
    # accuracy rather than average precision -- that line sat directly above a
    # valid kernel-conditioning reading which needed none of the absent fields,
    # and was the only measurement the report contained. The history belongs
    # here; what a stranger reads should just be accurate.
    need = ("method", "seed", "n_train", "n_test", "test_base_rate",
            "test_average_precision", "test_roc_auc")
    missing = [f for f in need if not has(recs, f)]
    if missing:
        return Outcome("schema", FAIL,
                       f"required fields missing from some records: "
                       f"{', '.join(missing)}. Discount the checks that name them "
                       f"below; the checks that do not need them still answer.")
    opt = [f for f in ("test_label_fingerprint", "shuffled", "final_converged")
           if not has(recs, f)]
    # `cell` was in that list and should not have been. Section 2 of the
    # protocol says configuration may be supplied EITHER as a nested `cell`
    # dict OR as top-level fields the audit infers, so warning about `cell`
    # when the inference succeeded warned about an absence the protocol
    # explicitly permits. It never showed on the one foreign file, which fails
    # on required fields above and never reaches this line. A file is missing
    # configuration only when it has neither route.
    if not has(recs, "cell") and not ctx.get("cell_fields"):
        opt.append("`cell`, and no top-level configuration field could be "
                   "inferred either")
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
    """A permuted-label run must sit at its null. The only evidence of no leak.

    THE SPREAD IS MEASURED OVER SPLITS, NOT OVER RECORDS
    ----------------------------------------------------
    A control file holds several methods and settings scored on each seed's
    split. Those records share the split, so they are not independent draws, and
    a standard error over records divides by the square root of the record count
    when the independent unit is the seed.

    This check shipped with that error. On an 80-record control that was 20
    seeds by 4 settings it reported +2.68 sigma and a FAIL. It is the fifth
    instance of the unit-of-analysis mistake in this project, the second inside
    the tool written to catch it, and it is why the warning about it is in the
    report at all rather than in a document nobody reads.
    """
    ctrl = ctx.get("control")
    if not ctrl:
        return Outcome("negative control", SKIP,
                       "no permuted-label control supplied (--control). Without one "
                       "there is no evidence the pipeline does not leak.")
    floor = ctx["floor"]
    by_split = all("seed" in r for r in ctrl)

    def units(fn):
        if not by_split:
            return [fn(r) for r in ctrl]
        g = defaultdict(list)
        for r in ctrl:
            g[r["seed"]].append(fn(r))
        return [float(np.mean(v)) for v in g.values()]

    out, bad = {}, []
    for label, fn, null in (("ROC-AUC", lambda r: float(r["test_roc_auc"]), 0.5),
                            ("normAP", norm_ap, 0.0)):
        vals = units(fn)
        m = float(np.mean(vals))
        se = (float(np.std(vals, ddof=1) / math.sqrt(len(vals)))
              if len(vals) > 1 else 0.0)
        z = (m - null) / se if se > 0 else 0.0
        # A sigma scales a deviation. When the deviation is itself below the
        # pipeline's reproducibility floor there is no deviation to scale, so
        # the figure is arithmetic rather than evidence and is NOT printed. The
        # verdict rule below has always required both conditions; the PASS line
        # printed the sigma anyway, and on a healthy control that is the common
        # case, not the edge case: a control that sits at its null has almost no
        # spread across splits by construction. Printing -4.8e+11 sigma on a
        # PASS invites a reader either to distrust the report or to quote the
        # number, and this check's own history is the first version dividing by
        # a standard error of order 1e-22 and reporting 3.5e+16 sigma on a mean
        # deviation of 0.000014.
        reportable = abs(m - null) > floor
        out[label] = {"mean": m, "sigma": z, "se": se, "n_units": len(vals),
                      "null": null, "sigma_reportable": reportable}
        # BOTH conditions, never the sigma alone. A control whose records are
        # near-identical has a standard error of order 1e-22, which is floating
        # point residue rather than a measured spread, and dividing by it turned
        # a deviation of 0.000014 into 3.5e16 sigma when this check was first
        # written. A deviation below the pipeline's own reproducibility floor is
        # not a leak however many sigma the arithmetic produces.
        if abs(z) > 2 and abs(m - null) > floor:
            bad.append(f"{label} {m:.4f} ({z:+.2f} sigma from {null})")
    n_units = out["ROC-AUC"]["n_units"]
    unit = (f"{n_units} splits ({len(ctrl)} records)" if by_split
            else f"{len(ctrl)} records, NO seed field so independence is ASSUMED")
    if bad:
        return Outcome("negative control", FAIL,
                       f"control deviates from its null by more than the {floor:g} "
                       f"floor over {unit}: {'; '.join(bad)}. Investigate before "
                       f"reading any result in the main file.", numbers=out)
    def say(label, fmt):
        d = out[label]
        if d["sigma_reportable"]:
            return f"{label} {d['mean']:{fmt}} ({d['sigma']:+.2f} sigma)"
        return (f"{label} {d['mean']:{fmt}}, within the {floor:g} floor of its null "
                f"of {d['null']:g}")
    said = f"{say('ROC-AUC', '.4f')}, {say('normAP', '+.4f')}"
    suppressed = [l for l in ("ROC-AUC", "normAP") if not out[l]["sigma_reportable"]]
    why = ""
    if suppressed:
        why = (f" No sigma is given for {' or '.join(suppressed)} because a deviation "
               f"below the pipeline's own reproducibility floor is not a leak however "
               f"many sigma the arithmetic produces, and the spread it would divide by "
               f"is floating-point residue rather than a measurement. That is the "
               f"healthy case for a control, not an edge case.")
    return Outcome("negative control", PASS, f"{unit}: {said}.{why}", numbers=out)


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
    methods = {r.get("method") for r in recs}
    if len(cells) < 2:
        # A single-configuration file still has independent units: the split.
        # This branch used to SKIP with "independent units cannot be identified",
        # which is false and skipped the warning exactly where the over-count is
        # easiest to make -- an 80-record file that is 20 splits scored by four
        # methods reads as 80 observations unless something says otherwise.
        if len(seeds) < 2 or len(recs) <= len(seeds):
            return Outcome("unit of analysis", SKIP,
                           "one configuration and at most one record per seed, so "
                           "records and independent units are the same thing here.")
        return Outcome("unit of analysis", WARN,
                       f"{len(recs)} records in ONE configuration = ~{len(seeds)} "
                       f"splits x {len(methods)} methods. Records sharing a split are "
                       f"not independent observations of it, so any claim about this "
                       f"configuration has n={len(seeds)}, not n={len(recs)}.",
                       numbers={"n_cells": 1, "n_seeds": len(seeds),
                                "n_methods": len(methods), "n_records": len(recs)})
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


def check_tuning_symmetry(recs, ctx):
    """Did both arms actually have something to tune?

    This started as a Tier 2 check on the grounds that knowing whether a kernel
    has a scale parameter needs the embedding. It does not. A method whose
    SELECTED hyperparameters never vary across records had nothing to select
    from; one whose parameters vary had a grid. The contrast is visible in the
    records alone.

    It is the check that would have caught this project's largest defect. The
    registered design gave the classical arm eleven RBF bandwidths spanning five
    decades and the quantum arm a fixed data scale, so one side was tuned and the
    other was not, and the comparison measured that asymmetry as much as it
    measured anything about quantum kernels. Nobody noticed for four weeks.

    It warns rather than fails: a method that always selects the same value might
    have a wide grid with one consistent winner, which is a different situation
    and not visible from selections alone. The report says which it cannot
    distinguish.
    """
    pool = list(recs) + list(ctx.get("compare") or [])
    if not any("params" in r or "C" in r for r in pool):
        return Outcome("tuning symmetry", SKIP,
                       "no `params` or `C` field, so it cannot be seen whether each "
                       "method had hyperparameters to select.")
    seen = defaultdict(lambda: {"params": set(), "C": set(), "n": 0,
                                "keys": set(), "had_dict": False})
    for r in pool:
        m = r.get("method", "?")
        seen[m]["n"] += 1
        if isinstance(r.get("params"), dict):
            seen[m]["had_dict"] = True
            seen[m]["keys"].update(r["params"].keys())
            seen[m]["params"].add(json.dumps(r["params"], sort_keys=True, default=str))
        if "C" in r:
            seen[m]["C"].add(str(r["C"]))
    # A method with NO structural parameters is not an untuned method, it is a
    # method with nothing to tune, and a linear kernel is the canonical case.
    # Without this distinction the check warned on every file containing a
    # linear baseline, which is most of them, and a check that fires on
    # everything carries no information. What is damning is a method that HAS
    # parameters and never varied them.
    table = {m: {"structural": len(v["params"]), "C": len(v["C"]), "records": v["n"],
                 "parameters": sorted(v["keys"]),
                 "has_parameters": bool(v["keys"])}
             for m, v in sorted(seen.items())}
    struct = {m: v["structural"] for m, v in table.items() if v["has_parameters"]}
    if len(struct) < 2:
        return Outcome("tuning symmetry", SKIP,
                       "fewer than two methods record their selected parameters.",
                       numbers={"per_method": table})
    lo, hi = min(struct.values()), max(struct.values())
    detail = "; ".join(f"{m} {v['structural']} structural / {v['C']} C"
                       + ("" if v["has_parameters"] else " (no parameters)")
                       for m, v in table.items())
    if lo <= 1 and hi >= 3:
        flat = {m: v["parameters"] for m, v in table.items()
                if v["has_parameters"] and v["structural"] <= 1}
        named = "; ".join(f"{m} (fixed: {', '.join(ps)})" for m, ps in flat.items())
        return Outcome("tuning symmetry", WARN,
                       f"methods differ sharply in what they were observed selecting: "
                       f"{detail}. {named} record parameters that never varied, so on "
                       f"this evidence those were fixed while other methods searched. "
                       f"If one arm's kernel width is tuned and the other's is fixed, "
                       f"the comparison measures that as much as it measures the "
                       f"kernels. A wide grid with one consistent winner looks "
                       f"identical here and is not the same thing; the records cannot "
                       f"tell them apart. Methods with no parameters at all, such as a "
                       f"linear kernel, are excluded rather than counted as untuned.",
                       numbers={"per_method": table, "fixed": flat})
    return Outcome("tuning symmetry", PASS,
                   f"every method varied its selection: {detail}.",
                   numbers={"per_method": table})


def check_conditioning(recs, ctx):
    """Tier 2: how ill-conditioned are the kernels, and what does that forbid?

    Needs the Gram matrices, so it runs only with a hook exposing gram(record).
    """
    hook = ctx.get("hook")
    fn = getattr(hook, "gram", None) if hook else None
    if fn is None:
        return Outcome("kernel conditioning", NOT_RUN,
                       "needs the Gram matrices. Provide --hook with a module "
                       "exposing gram(record) -> ndarray. An ill-conditioned kernel "
                       "makes the SVM dual underdetermined, so decision scores move "
                       "at machine precision and any threshold-based test is invalid.",
                       tier=2)
    sample = _sample(recs, ctx.get("hook_sample", 6), ctx.get("cell_fields"))
    conds, failed, taken = [], 0, []
    for r in sample:
        try:
            K = np.asarray(fn(r), dtype=float)
            conds.append(float(np.linalg.cond(K)))
            taken.append(r)
        except Exception:
            failed += 1
    if not conds:
        return Outcome("kernel conditioning", NOT_RUN,
                       f"the hook's gram() raised on all {failed} sampled records.",
                       tier=2)
    worst = max(conds)
    num = {"n_sampled": len(conds), "cond_min": min(conds), "cond_max": worst,
           "gram_errors": failed, "coverage": _coverage(taken),
           "methods_sampled": sorted({str(r.get("method")) for r in taken})}
    if worst > 1e12:
        return Outcome("kernel conditioning", WARN,
                       f"condition number reaches {worst:.1e} over {len(conds)} sampled "
                       f"kernels covering {_coverage(taken)}. The dual is underdetermined at that conditioning, so "
                       f"decision scores are reproducible only to a floor you must "
                       f"measure and quote, and threshold-based tests such as McNemar "
                       f"are not usable. Rank statistics survive; check that yours are.",
                       tier=2, numbers=num)
    return Outcome("kernel conditioning", PASS,
                   f"condition number stays below 1e12 (worst {worst:.1e} over "
                   f"{len(conds)} sampled kernels covering {_coverage(taken)}), so the "
                   f"dual is well determined.",
                   tier=2, numbers=num)


def _sort_key(r, fields):
    """Configuration first, then seed as a NUMBER. Sorting seeds as strings puts
    seed 10 next to seed 1, which quietly undoes the spread this exists for."""
    try:
        seed = (0, float(r.get("seed")))
    except (TypeError, ValueError):
        seed = (1, str(r.get("seed")))
    return (str(cell_of(r, fields)), seed)


def _sample(recs, k, fields=None):
    """Choose k records that actually span the methods being compared.

    A stride (recs[::len(recs)//k]) is the obvious way to spread a sample and it
    is wrong, because it aliases with the order records were written in. This
    project's files are written configuration-major, then seed, then setting, in
    blocks of (settings x seeds); a stride of 200 against a block period of 80
    lands on setting index 0 every single time. The first real run returned six
    records that were all the same method on two seeds, and every hook-based
    number in that report described one kernel family while the text called it a
    sample of the file.

    So the sample is stratified by method and spread across configurations and
    seeds within each, deterministically. The methods it landed on are reported
    with the result, because a sample that cannot be seen is a sample that can
    quietly become one family again.
    """
    by_method = defaultdict(list)
    for r in recs:
        by_method[r.get("method")].append(r)
    methods = sorted(by_method, key=str)
    for v in by_method.values():
        v.sort(key=lambda r: _sort_key(r, fields))
    # Ceiling, not floor: with k=6 and four methods, floor division takes one
    # each and returns four. The round robin below truncates the surplus, so
    # every method appears before any method appears twice.
    per = max(1, -(-k // max(1, len(methods))))
    picks = []
    for i, m in enumerate(methods):
        v = by_method[m]
        n = min(per, len(v))
        if not n:
            picks.append([])
            continue
        step = max(1, len(v) // n)
        # Stagger each method's start. Without it every method is sampled at the
        # same offsets, so the sample spans the methods but lands on the same
        # two seeds for all of them -- half the aliasing, silently retained.
        off = (i * step // max(1, len(methods))) % len(v)
        picks.append([v[min(off + j * step, len(v) - 1)] for j in range(n)])
    out = []
    for row in zip_longest(*picks):          # round robin, so a small k still spans
        for r in row:
            if r is not None and len(out) < k:
                out.append(r)
    return out[:k]


def _coverage(rows):
    """What the sample actually covered, for the report."""
    ms = sorted({str(r.get("method")) for r in rows})
    ss = sorted({str(r.get("seed")) for r in rows})
    return f"{len(ms)} method(s) ({', '.join(ms)}) on {len(ss)} seed(s)"


def _fit_gamma(X, K):
    """Least squares over a log-spaced gamma grid, then a local refine.

    No label, no test point and no score enters this: the surrogate is fitted to
    the kernel, not to the thing it is afterwards scored on. That is what makes
    a match damning rather than circular.
    """
    sq = np.sum((X[:, None, :] - X[None, :, :]) ** 2, axis=-1)
    best, err = None, np.inf
    grid = np.logspace(-5, 3, 81)
    for _ in range(2):
        for g in grid:
            e = float(np.mean((np.exp(-g * sq) - K) ** 2))
            if e < err:
                best, err = float(g), e
        grid = np.linspace(max(best * 0.5, 1e-9), best * 1.5, 41)
    return best, float(np.sqrt(err))


def check_surrogate(recs, ctx):
    """Tier 2: does the kernel do anything its nearest classical kernel cannot?

    The question a benchmark exists to answer, and the one its results file
    cannot. A quantum kernel that scores what a label-free RBF fitted to it
    scores IS that RBF, whatever its distance in kernel space, and every figure
    reported about it is a figure about a Gaussian kernel computed expensively.

    Kernel-space distance does not settle it and no threshold on it can: nothing
    says Spearman 0.998 is the same model and 0.99 is not. So this does not
    measure distance. It fits the surrogate, runs it through the caller's own
    pipeline on the caller's own split, and compares out-of-sample in the units
    the endpoints are already in.
    """
    hook = ctx.get("hook")
    need = [n for n in ("gram", "training_data", "refit")
            if getattr(hook, n, None) is None]
    if need:
        return Outcome("classical surrogate equivalence", NOT_RUN,
                       f"needs {', '.join(need)} in --hook. Fits the nearest "
                       f"classical kernel with no labels and runs it through your "
                       f"pipeline on your split; a kernel that scores what its "
                       f"surrogate scores is that surrogate.", tier=2)
    sample = _sample(recs, ctx.get("hook_sample", 6), ctx.get("cell_fields"))
    rows, errors = [], 0
    for r in sample:
        try:
            K = np.asarray(hook.gram(r), dtype=float)
            X, _ = hook.training_data(r)
            g, rmse = _fit_gamma(np.asarray(X, dtype=float), K)
            sur = hook.refit(r, g)
            rows.append({"method": r.get("method"), "seed": r.get("seed"),
                         "gamma": g, "gram_rmse": rmse,
                         "d_normap": norm_ap(r) - norm_ap(sur)})
        except Exception as exc:
            errors += 1
            if "different split" in str(exc):
                return Outcome("classical surrogate equivalence", FAIL,
                               f"the hook rebuilt a different split than the "
                               f"records were scored on, so nothing computed from "
                               f"it is comparable: {exc}", tier=2)
    if not rows:
        return Outcome("classical surrogate equivalence", NOT_RUN,
                       f"the hook raised on all {errors} sampled records.", tier=2)
    d = np.array([r["d_normap"] for r in rows])
    ad = np.abs(d)
    med, lo_d, hi_d = float(np.median(ad)), float(ad.min()), float(ad.max())
    below = int((ad < ctx["floor"]).sum())
    cover = (f"{len({r['method'] for r in rows})} method(s) "
             f"({', '.join(sorted({str(r['method']) for r in rows}))}) on "
             f"{len({r['seed'] for r in rows})} seed(s)")
    num = {"n_sampled": len(rows), "median_abs_d_normap": med,
           "min_abs_d_normap": lo_d, "max_abs_d_normap": hi_d,
           "n_below_floor": below, "coverage": cover,
           "methods_sampled": sorted({str(r["method"]) for r in rows}),
           "signed_median": float(np.median(d)), "hook_errors": errors,
           "per_record": rows}
    # A median clearing the floor while individual records sit under it is not a
    # separation, it is a sample straddling the resolution limit. The first
    # version of this check had a single threshold on the median and returned a
    # confident PASS at 0.0012 against a floor of 0.0010 -- 1.2x the limit, on 6
    # samples, with no spread reported. The full per-family analysis of the same
    # arm concludes the kernel IS its surrogate. The measurement agreed with
    # that analysis; only the verdict rule disagreed.
    if below and med >= ctx["floor"]:
        return Outcome("classical surrogate equivalence", WARN,
                       f"too close to call: median difference from a label-free RBF "
                       f"surrogate is {med:.2e} in normAP but {below} of {len(rows)} "
                       f"sampled kernels fall below the {ctx['floor']:.0e} "
                       f"reproducibility floor (range {lo_d:.2e} to {hi_d:.2e}). A "
                       f"median above the floor with records beneath it is a sample "
                       f"straddling the resolution limit, not a separation. The "
                       f"sample covered {cover}; a spread that wide within one family "
                       f"is a different situation from one between families, and only "
                       f"the full per-family analysis distinguishes them.",
                       tier=2, numbers=num)
    if med < ctx["floor"]:
        return Outcome("classical surrogate equivalence", WARN,
                       f"over {len(rows)} sampled kernels the median difference "
                       f"from a label-free RBF surrogate is {med:.2e} in normAP, "
                       f"below this pipeline's reproducibility floor of "
                       f"{ctx['floor']:.0e}, over {cover}. On this evidence the kernel is its "
                       f"surrogate and the comparison is classical-versus-classical. "
                       f"Sampled, so it indicates rather than establishes; run the "
                       f"full set before reporting either way.", tier=2, numbers=num)
    return Outcome("classical surrogate equivalence", PASS,
                   f"every one of {len(rows)} sampled kernels separates from its "
                   f"nearest classical surrogate, median {med:.4f} in normAP, range "
                   f"{lo_d:.2e} to {hi_d:.2e}, all above the {ctx['floor']:.0e} floor, "
                   f"covering {cover}. "
                   f"That is the size of what the non-classical structure is worth "
                   f"here, in endpoint units, and it carries no sign about the best "
                   f"classical kernel: a kernel can separate from its surrogate and "
                   f"still lose to it.", tier=2, numbers=num)


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
    a, b = defaultdict(lambda: defaultdict(list)), defaultdict(lambda: defaultdict(list))
    for r in recs:
        a[(r["seed"], cell_of(r, fields))][r["method"]].append(r)
    for r in other:
        b[(r["seed"], cell_of(r, ctx["compare_fields"]))][r["method"]].append(r)

    # A (seed, configuration, method) key that holds more than one record means
    # the configuration fields do not identify a single result, so there is no
    # such thing as THE record to pair with and any pairing picks one
    # arbitrarily. This mattered: handed a single-configuration quantum file and
    # a fifteen-configuration classical file, the field intersection came out
    # empty, all fifteen configurations collapsed onto one key, and the earlier
    # version of this check kept whichever record it read last and reported a
    # clean PASS with a plausible minimum detectable effect computed from the
    # wrong pairs. That is D6's error, committed by the check written to catch
    # D6's error. The label fingerprint did not save it, because configurations
    # differ in the feature mapping and not in the labels.
    dup = [(k, m, len(v)) for side in (a, b) for k, mm in side.items()
           for m, v in mm.items() if len(v) > 1]
    if dup:
        worst = max(dup, key=lambda t: t[2])
        return Outcome("cross-arm comparison", FAIL,
                       f"{len(dup)} (seed, configuration, method) groups hold more "
                       f"than one record, up to {worst[2]} for method "
                       f"{worst[1]!r}. The configuration fields "
                       f"{fields or '(none)'} do not identify a single result, so "
                       f"pairs cannot be formed without choosing arbitrarily and no "
                       f"power figure from this pairing would be meaningful. Pass "
                       f"--cell-fields naming the fields that define a configuration "
                       f"in BOTH files, or restrict the comparison file to the "
                       f"configuration this one covers.",
                       numbers={"ambiguous_groups": len(dup),
                                "max_records_per_group": worst[2],
                                "cell_fields": list(fields)})

    keys = sorted(set(a) & set(b), key=str)
    if not keys:
        return Outcome("cross-arm comparison", FAIL,
                       "no (seed, configuration) group appears in both files, so the "
                       "two arms cannot be paired at all. Check that both were run on "
                       "the same splits and configurations.")

    mismatched, unverifiable = [], 0
    for k in keys:
        fps = {r[0].get("test_label_fingerprint")
               for r in list(a[k].values()) + list(b[k].values())}
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
                diffs[(cell, ma, mb)].append(norm_ap(ra[0]) - norm_ap(rb[0]))
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
    rc = rank_correlation([float(x["inner_score"]) for x in recs],
                          [norm_ap(x) for x in recs])
    if not rc.ok:
        # This check previously PASSED here. scipy returns NaN on a constant
        # input, `nan <= 0` is False, so the WARN branch below never fired and
        # the audit reported "selection is auditable" on a correlation that does
        # not exist. That is the same failure the comment below describes having
        # already fixed once: a measurement taken and then not used. A check
        # that cannot answer its question SKIPs and names why, exactly as it
        # does for a missing field -- it never reads absence as a pass.
        return Outcome("selection", SKIP,
                       f"selection cannot be audited from these records: "
                       f"{rc.why} With {rc.n} records there is nothing to "
                       f"correlate, so this says nothing about whether "
                       f"selection used the inner score or the test score.",
                       numbers={"n_records": rc.n})
    r = rc.rho
    num = {"spearman_inner_vs_test": r}
    # THE SIGN IS THE BOUNDARY, and it is qualitative rather than a chosen
    # threshold. A correlation that is not positive means the selection
    # criterion carries no information about the quantity it selects for, which
    # is a statement about direction and needs no threshold to make.
    #
    # Why no magnitude threshold is used, and why the PASS message therefore
    # reports the number without interpreting it: any cut-off on how strongly a
    # criterion must track its endpoint would be chosen rather than derived, and
    # a chosen threshold presented as a verdict is the defect this protocol
    # exists to report. Section 5.6 of the paper collects three instances of it.
    #
    # The cost of that choice is that a PASS covers +0.001 and +0.999 alike. The
    # message says so rather than papering over it: until 26 October 2026 it read
    # "selection is auditable and the criterion tracks the endpoint", which on a
    # demonstration run asserted tracking at +0.098. The verdict was right and
    # the sentence was not.
    #
    # This check used to compute that number, print it, and PASS regardless. It
    # returned "Selection auditable" on an arm whose correlation was -0.367,
    # which is the same failure as the two verdict-rule defects found earlier
    # this week: a measurement taken correctly and then not used.
    if r <= 0:
        return Outcome("selection", WARN,
                       f"selection used an inner score, but that score does not "
                       f"predict out-of-sample performance here: rank correlation "
                       f"{r:+.3f}. Tuning is then ranking noise. That is consistent "
                       f"with candidates which are genuinely equivalent -- check the "
                       f"surrogate and precision-floor results above before reading it "
                       f"as a broken selection rule -- and either way it means the "
                       f"tuning bought nothing. It does not invalidate the held-out "
                       f"estimates.", numbers=num)
    return Outcome("selection", PASS,
                   f"an inner selection score is recorded alongside the test "
                   f"scores, and their observed rank correlation is {r:+.3f}, "
                   f"which is positive. That is the whole of what this says: "
                   f"selection had an inner criterion available and that "
                   f"criterion is not anti-correlated with the endpoint. "
                   f"NO assessment of the strength of association or of "
                   f"statistical significance is made. The magnitude is reported "
                   f"and not judged, because this check's boundary is the sign.",
                   numbers=num)


# ----------------------------------------------------------------- tier 2

# Still not runnable from records, with the hook function each would need.
# "bandwidth tuning" used to be here and is now the Tier 1 `tuning symmetry`
# check: whether an arm had a parameter to tune is visible in what it selected.
TIER2 = [
    ("grid adequacy against a shuffled null",
     "needs a re-run, not a hook: the same pipeline on permuted labels with a widened "
     "grid. Widening raises the best inner score even when nothing is better, so "
     "hyperparameter edge flags never justify it on their own."),
]

# Fields a check cannot work without, declared rather than discovered.
#
# The first foreign audit this protocol ever ran -- against the Kakavand et al.
# hardware deposit, whose endpoint is balanced accuracy rather than average
# precision -- produced three checks reporting `check raised KeyError('n_test')`
# as a FAIL. That reads to a stranger as a broken tool rather than as a file
# that does not carry the field, and it is wrong twice over: the question was
# unanswerable, not failed, and `check_schema` had already named every absent
# field one line earlier. A check that needs a field it has not got must SKIP
# and say which field, exactly as the checks with optional fields already do.
REQUIRES = {
    check_chance_correction: ("chance correction",
                              ("n_test", "test_base_rate")),
    check_power: ("statistical power",
                  ("test_average_precision", "n_test", "test_base_rate")),
    check_precision_floor: ("precision floor",
                            ("test_average_precision", "n_test",
                             "test_base_rate")),
    check_unit_of_analysis: ("unit of analysis", ("seed",)),
    check_multiplicity: ("multiplicity", ("method",)),
    check_cross_arm: ("cross-arm comparison", ("seed", "method")),
}

def check_cost_claim_support(recs, ctx):
    """Tier 1: can this file support any statement about what a QPU run cost?

    D18 of the research project this came out of is why this exists. That
    project reported a pairwise circuit count and four of its documents called
    it the hardware-equivalent cost of the experiment. It is not. Hardware runs
    each pairwise circuit once per SHOT, so the executions a QPU meters are the
    circuit count times the shot count, and that project recorded no shot count
    anywhere -- not in its registration, not in its paper, not in any field of
    any of its 15,120 records. The figure understated hardware cost by three
    orders of magnitude and was used to decide what was feasible.

    So a file claiming anything about QPU cost needs the shots per entry, the
    backend, and the metered quantum seconds. Absence is a limitation stated in
    full. It is never a pass, and provenance is never guessed from a method
    name: a record saying `method: "hardware"` with no `provenance` field has
    not told this tool it ran on a QPU.
    """
    s = prov.provenance_summary(recs)
    n, counts, present = s["n_records"], s["counts"], s["cost_fields_present"]
    on_hw = s["cost_fields_present_on_hardware"]
    declared = n - counts.get(prov.UNSTATED, 0)
    hw = s["n_declared_hardware"]
    where = ", ".join(f"{f} on {present[f]} of {n}" for f in prov.COST_FIELDS)
    nums = {"n_records": n, "n_declared_hardware": hw, "n_declared": declared,
            "cost_fields_present": present,
            "cost_fields_present_on_hardware": on_hw}

    if not hw:
        if not declared:
            why = (f"no record declares `provenance`, so this file does not state that "
                   f"any number came from a QPU and no QPU-cost claim is in scope")
        else:
            why = (f"{declared} of {n} records declare `provenance` and none of them is "
                   f"hardware, so no QPU-cost claim is in scope")
        return Outcome("hardware cost claims", SKIP,
                       f"{why}. Present anyway: {where}. Declare `provenance` "
                       f"(see FIELDS.md) if a hardware claim is being made.",
                       numbers=nums)

    # Scoped to the hardware records. A classical or simulator record has no
    # shots to report and is not what a cost claim rests on.
    absent = [f for f in prov.COST_FIELDS if on_hw[f] == 0]
    partial = [f for f in prov.COST_FIELDS if 0 < on_hw[f] < hw]
    if absent or partial:
        bits = []
        if absent: bits.append("absent entirely: " + ", ".join(absent))
        if partial: bits.append("on only some of them: " + ", ".join(partial))
        return Outcome("hardware cost claims", WARN,
                       f"{hw} of {n} records declare hardware provenance, and of those, "
                       f"{'; '.join(bits)}. LIMITATION: this file supports no statement "
                       f"about QPU time, cost, or whether the run was feasible within an "
                       f"allocation. A circuit or pair count is not a cost; hardware runs "
                       f"each circuit once per shot. Results claims are unaffected.",
                       numbers=nums)

    hwrecs = prov.hardware_records(recs)
    shots = [int(r["shots"]) for r in hwrecs]
    secs = [float(r["quantum_seconds"]) for r in hwrecs]
    backends = sorted({str(r["backend"]) for r in hwrecs})
    nums.update({"total_shots": sum(shots), "total_quantum_seconds": sum(secs),
                 "backends": backends})
    return Outcome("hardware cost claims", PASS,
                   f"{hw} of {n} records declare hardware provenance and all carry "
                   f"shots, backend and quantum_seconds: {sum(shots):,} shots and "
                   f"{sum(secs):,.1f} metered QPU seconds across "
                   f"{len(backends)} backend(s) ({', '.join(backends)}). A cost claim "
                   f"from this file is checkable.",
                   numbers=nums)


CHECKS = [check_schema, check_chance_correction, check_negative_control, check_pairing,
          check_convergence, check_unit_of_analysis, check_power,
          check_precision_floor, check_multiplicity, check_tuning_symmetry,
          check_cross_arm, check_conditioning, check_surrogate,
          check_selection_leak, check_cost_claim_support]


def load_hook(path):
    """Import a user-supplied adapter so Tier 2 checks can reach the kernels.

    The audit cannot import someone else's pipeline, so the pipeline hands it a
    small module instead. Every function is optional; a check that needs one it
    does not find reports NOT RUN and names the function, rather than guessing.
    """
    if not path:
        return None
    import importlib.util
    spec = importlib.util.spec_from_file_location("audit_hook", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(path, control, floor, cell_fields=None, compare=None, hook=None,
        hook_sample=6):
    recs = load(path)
    if not recs:
        print(f"{path}: empty")
        return 2, []
    fields = cell_fields if cell_fields is not None else infer_cell_fields(recs)
    other = load(compare) if compare else None
    # Both arms MUST be grouped by the same fields or no cell tuple can ever
    # match and the cross-arm check fails for a reason that looks like a data
    # problem. Intersect the two inferences rather than letting each file
    # decide for itself.
    if other is not None and cell_fields is None:
        theirs = infer_cell_fields(other)
        shared = [f for f in fields if f in theirs]
        if shared != fields or shared != theirs:
            print(f"  NOTE: the two arms inferred different configuration fields "
                  f"({fields} and {theirs}); using their intersection {shared}.")
        fields = shared
    ctx = {"control": load(control) if control else None, "floor": floor,
           "cell_fields": fields, "compare": other, "compare_fields": fields,
           "hook": load_hook(hook), "hook_sample": hook_sample}
    outs = []
    for fn in CHECKS:
        req = REQUIRES.get(fn)
        if req:
            name, needed = req
            absent = [f for f in needed if not has(recs, f)]
            if absent:
                outs.append(Outcome(
                    name, SKIP,
                    f"records do not carry {', '.join(absent)}, so this "
                    f"question cannot be answered from this file. That is a "
                    f"property of the records, not a failure of the check."))
                continue
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
    ap.add_argument("--hook",
                    help="path to a Python module exposing gram(record), "
                         "training_data(record) and/or refit(record, K), which lets "
                         "the Tier 2 checks reach your kernels. See "
                         "scripts/audit_hook_qbench.py for a worked example.")
    ap.add_argument("--hook-sample", type=int, default=6,
                    help="records to sample for hook-based checks (they recompute "
                         "kernels, so this is the cost knob)")
    ap.add_argument("--json", help="write the report here")
    args = ap.parse_args()

    fields, outs = run(args.results, args.control, args.floor, args.cell_fields,
                       args.compare, args.hook, args.hook_sample)

    print(f"\nAUDIT: {args.results}")
    print("This audits METHOD, not results. It never says which model won.")
    if fields:
        print(f"  Configuration grouped by: {', '.join(fields)}"
              f"{' (given)' if args.cell_fields else ' (inferred from the data)'}. "
              f"Override with --cell-fields if that is wrong.")
    else:
        print("  No configuration fields found, so every record is treated as one "
              "cell. Pass --cell-fields if this file has configurations.")

    recs = load(args.results)
    psum = prov.provenance_summary(recs)
    print("\n  WHERE THIS DATA CAME FROM, as the file itself declares it:")
    for line in prov.provenance_banner(psum):
        print(f"    {line}")
    print()
    width = max(len(o.name) for o in outs)
    for o in outs:
        print(f"  [{o.status:^7}] {o.name:<{width}}  {o.detail}")

    if TIER2:
        print(f"\n  Not runnable from records alone:")
        for name, why in TIER2:
            print(f"  [{NOT_RUN:^7}] {name}")
            print(f"            {why}")

    print("\n  WHAT VALIDATES THESE CHECKS")
    for line in prov.validation_banner():
        print(f"    {line}" if line else "")

    counts = {s: sum(o.status == s for o in outs) for s in (PASS, WARN, FAIL, SKIP)}
    counts[NOT_RUN] = sum(o.status == NOT_RUN for o in outs)
    print(f"\n  {counts[PASS]} passed, {counts[WARN]} warnings, {counts[FAIL]} failed, "
          f"{counts[SKIP]} skipped for missing fields.")
    if counts[SKIP] or counts[NOT_RUN]:
        print(f"  {counts[SKIP] + counts[NOT_RUN]} question(s) were NOT ANSWERED. A SKIP "
              f"is missing evidence, not a passed check, and nothing above should be read "
              f"as this file having satisfied those checks.")
    if counts[FAIL]:
        print("  A FAIL means a conclusion drawn from this file is not supported BY "
              "this file. It does not mean the conclusion is wrong.")

    if args.json:
        p = Path(args.json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(
            {"file": args.results, "control": args.control, "floor": args.floor,
             # axes 2 and 3 per check, with axis 4 beside each
             "checks": [dict(vars(o), external_validation=prov.validation_for(o.name))
                        for o in outs],
             "not_runnable": [{"name": n, "reason": w} for n, w in TIER2],
             # Everything below is additive and exists because extracting this
             # package found the research repository's own committed report
             # could not reproduce itself: it stored file, control and floor and
             # not the hook sample that moved its only Tier 2 measurement by a
             # factor of 26. See EXTRACTION.md.
             "qaudit_version": __version__,
             "invocation": {"results": args.results, "control": args.control,
                            "floor": args.floor,
                            "cell_fields_given": args.cell_fields,
                            "cell_fields_used": fields,
                            "compare": args.compare, "hook": args.hook,
                            "hook_sample": args.hook_sample},
             "environment": prov.environment(),
             "environment_note": prov.environment_note(),
             "data_provenance": psum,
             "external_evidence": prov.EXTERNAL_EVIDENCE_NOTE},
            indent=2, default=float) + "\n")
        print(f"\n-> {p}")

    sys.exit(2 if counts[FAIL] else (1 if counts[WARN] else 0))


if __name__ == "__main__":
    main()
