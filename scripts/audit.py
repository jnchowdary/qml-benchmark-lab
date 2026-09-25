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


def cell_of(r):
    """The configuration a record belongs to. Records sharing a cell and a seed
    are the same split scored by different methods, which is what makes them
    pairable.

    With no `cell` field every record falls into ONE cell. Falling back to the
    method would be worse than useless: it would put each method in its own
    configuration, so nothing would ever pair, and the audit would report no
    comparisons on a file full of them.
    """
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
        groups[(r["seed"], cell_of(r))].add(r["test_label_fingerprint"])
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
    cells = {cell_of(r) for r in recs}
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
        by_cell[cell_of(r)][r["seed"]][r["method"]] = norm_ap(r)
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
        by_cell[cell_of(r)][r["seed"]][r["method"]] = norm_ap(r)
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
        by_cell[cell_of(r)].add(r["method"])
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
          check_precision_floor, check_multiplicity, check_selection_leak]


def run(path, control, floor):
    recs = load(path)
    if not recs:
        print(f"{path}: empty")
        return 2, []
    ctx = {"control": load(control) if control else None, "floor": floor}
    outs = []
    for fn in CHECKS:
        try:
            outs.append(fn(recs, ctx))
        except Exception as exc:                      # a broken check is a failure
            outs.append(Outcome(fn.__name__, FAIL, f"check raised {exc!r}"))
    return None, outs


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("results")
    ap.add_argument("--control", help="permuted-label companion file")
    ap.add_argument("--floor", type=float, default=DEFAULT_PRECISION_FLOOR,
                    help="reproducibility floor of the pipeline, in normAP")
    ap.add_argument("--json", help="write the report here")
    args = ap.parse_args()

    _, outs = run(args.results, args.control, args.floor)

    print(f"\nAUDIT: {args.results}")
    print("This audits METHOD, not results. It never says which model won.\n")
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
