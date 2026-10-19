#!/usr/bin/env python3
"""The registered grid-adequacy decision, and nothing else.

WHY THIS IS ITS OWN FILE
------------------------
Section 7 of the pre-registration names `scripts/check_grid_edges.py` as what
decides whether a hyperparameter grid is too narrow, and requires the decision
to be made against a shuffled-label null. That script measures as well as
decides, so importing it pulls in numpy, joblib, scikit-learn and the whole
`qbench` package before a single line runs. The decision itself reads two JSON
files and subtracts two numbers.

The consequence was that nobody could check the registered decision without
first installing the research environment, which is the opposite of what §5 of
the paper claims for the cheap end of this protocol: seconds, and no access to
the originating pipeline. This module imports `json` and `pathlib` and nothing
else, so a reader with the two stored runs and a bare Python can reproduce the
adjudication in a second.

`check_grid_edges.py` imports these names rather than defining them, so there is
one implementation and not two.

THE DECISION
------------
Extending a grid raises the maximum inner-CV score even when no searched point
is genuinely better, because the maximum of a noisy surface grows with the
number of points searched. So the gain from widening on real labels is evidence
of under-tuning only insofar as it EXCEEDS the gain from widening on permuted
labels, where there is no signal and the whole gain is that selection noise.

The threshold is 0.002, declared in docs/week-03-report.md section 14 before the
comparison was made and unchanged since. Neither the mean nor the maximum
statistic was nominated in advance, so both are reported and SPLIT is returned
if they ever disagree rather than one being chosen after the fact.

Usage:
    python3 scripts/adjudicate_grid.py results/analysis/grid_edges_churn_both.json \
                                       results/analysis/grid_edges_churn_both_shuffled.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Pre-declared in docs/week-03-report.md section 14, BEFORE the comparison was
# made. It lived in prose for three weeks while check_grid_edges.py printed a
# verdict that did not use it.
EXCESS_THRESHOLD = 0.002

# A real run and a null run are comparable only if all of these agree.
# Subtracting one experiment's selection noise from another experiment's gain
# measures nothing, so a mismatch is refused by name rather than averaged over.
COMPARABLE_ON = ("dataset", "n_per_class", "direction", "seeds", "mappings",
                 "qubits", "c_grid", "extension")


def load_run(path):
    """Load a stored run, refusing anything that is not one of this script's."""
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"\n  no such run: {p}\n")
    d = json.loads(p.read_text(encoding="utf-8"))
    missing = [k for k in ("summaries", "shuffled", *COMPARABLE_ON) if k not in d]
    if missing:
        raise SystemExit(
            f"\n  {p}\n"
            f"  does not carry {', '.join(missing)}. Either it is not a run this\n"
            f"  script wrote, or it predates the fields the adjudication needs.\n"
            f"  Re-run it rather than adjudicating against it.\n")
    return d


def adjudicate(real, null, threshold=EXCESS_THRESHOLD):
    """The registered decision: real-label gain MINUS shuffled-label gain.

    Until this existed, check_grid_edges.py computed the null when asked,
    printed it, told the reader to do the subtraction by hand, and on a real run
    with --mde printed a verdict derived from the MDE instead. Week 3 had
    already recorded that MDE rule as the defect: the expected maximum over a
    grid grows with the number of points searched, so the ratio cannot separate
    "the optimum lies outside the grid" from "the surface is too noisy to rank".
    It said AMBIGUOUS on churn and UNDER-TUNED on fraud, where the adjudicated
    answer on the same stored runs is that the frozen grid is adequate on both.
    """
    if real.get("shuffled"):
        raise SystemExit("\n  the first run is a null run: the arguments are the "
                         "wrong way round.\n")
    if not null.get("shuffled"):
        raise SystemExit("\n  the second run has shuffled=false, so it carries "
                         "signal and is not a null.\n")
    bad = [k for k in COMPARABLE_ON if real.get(k) != null.get(k)]
    if bad:
        raise SystemExit(
            "\n  NOT COMPARABLE. These differ between the real run and the null:\n"
            + "".join(f"    {k}:\n      real {real.get(k)!r}\n      null {null.get(k)!r}\n"
                      for k in bad)
            + "  Re-run the null with matching settings.\n")

    rn = {s["kernel"]: s for s in real["summaries"]}
    nn = {s["kernel"]: s for s in null["summaries"]}
    shared = sorted(set(rn) & set(nn))
    if not shared:
        raise SystemExit("\n  the two runs share no kernel.\n")

    per = [{
        "kernel": k,
        "real_mean": rn[k]["mean_gain"], "null_mean": nn[k]["mean_gain"],
        "real_max": rn[k]["max_gain"], "null_max": nn[k]["max_gain"],
        "excess_mean": rn[k]["mean_gain"] - nn[k]["mean_gain"],
        "excess_max": rn[k]["max_gain"] - nn[k]["max_gain"],
    } for k in shared]

    worst_mean = max(p["excess_mean"] for p in per)
    worst_max = max(p["excess_max"] for p in per)
    crossed = [n for n, v in (("mean", worst_mean), ("max", worst_max)) if v > threshold]
    outcome = "ADEQUATE" if not crossed else ("WIDEN" if len(crossed) == 2 else "SPLIT")
    return {"threshold": threshold, "kernels": shared, "per_kernel": per,
            "worst_excess_mean": worst_mean, "worst_excess_max": worst_max,
            "crossed": crossed, "outcome": outcome}


def print_adjudication(a, source=None):
    print("\nREGISTERED ADJUDICATION  (real-label gain minus shuffled-label gain)")
    if source:
        print(f"  null run: {source}")
    print(f"  {'kernel':<9}{'real mean':>11}{'null mean':>11}{'excess':>11}"
          f"{'real max':>11}{'null max':>11}{'excess':>11}")
    for p in a["per_kernel"]:
        print(f"  {p['kernel']:<9}{p['real_mean']:>+11.5f}{p['null_mean']:>+11.5f}"
              f"{p['excess_mean']:>+11.5f}{p['real_max']:>+11.5f}"
              f"{p['null_max']:>+11.5f}{p['excess_max']:>+11.5f}")
    print(f"\n  threshold for widening, pre-declared : {a['threshold']:+.5f}")
    print(f"  worst excess, mean statistic         : {a['worst_excess_mean']:+.5f}")
    print(f"  worst excess, max statistic          : {a['worst_excess_max']:+.5f}")
    if a["outcome"] == "ADEQUATE":
        print("\n  ADEQUATE. Neither statistic exceeds the threshold on any kernel, so")
        print("  widening buys no more on signal than it buys on noise. The frozen grid")
        print("  stands, no re-run is required, and the edge flags are the winner's")
        print("  curse. Edge flags alone never justify widening a grid.")
    elif a["outcome"] == "WIDEN":
        print("\n  WIDEN. Both statistics exceed the threshold, so the gain is not")
        print("  explained by the maximum of a noisy surface growing with the number of")
        print("  points searched. Widen the grids and re-run the affected arm.")
    else:
        print(f"\n  SPLIT. The {a['crossed'][0]} statistic exceeds the threshold and the")
        print("  other does not, so the answer depends on which statistic is chosen.")
        print("  This module will not choose. Report both and decide in the record.")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        raise SystemExit(
            "\n  usage: python3 scripts/adjudicate_grid.py <real.json> <null.json>\n"
            "\n  Both are runs written by scripts/check_grid_edges.py: the first on\n"
            "  real labels, the second with --shuffle-labels. Nothing is computed\n"
            "  and nothing is written.\n")
    print_adjudication(adjudicate(load_run(argv[0]), load_run(argv[1])), source=argv[1])


if __name__ == "__main__":
    main()
