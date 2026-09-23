#!/usr/bin/env python3
"""What effect size can this design actually detect? Answered from week-3 data.

The question this settles
-------------------------
The whole project rests on a comparison: quantum kernel against classical
kernel, paired over 10 seeds. If that design can only detect a difference of
0.11 PR-AUC, then "no significant quantum advantage" is a statement about the
experiment's resolution, not about quantum kernels, and the paper must say so
in the abstract rather than in a limitations paragraph nobody reads.

Nothing here needs a new experiment. Week 3 already produced 10 paired seeds
per cell for three classical kernels. The spread of those paired differences
is the same spread the quantum comparison will have, because it comes from the
same splits, the same subsample size and the same test-set size. Kernel choice
changes the mean of the differences, not materially their variance.

What it computes
----------------
1. The standard deviation of the PAIRED per-seed difference, per cell, for
   every pair of classical kernels. That is the noise floor.
2. The minimum detectable effect (MDE) at n=10 seeds: the smallest true mean
   difference that would be found significant 80% of the time by a two-sided
   paired t-test at alpha=0.05. Solved exactly from the non-central t
   distribution, not from the normal approximation, because at df=9 the
   approximation understates the MDE by roughly 15%.
3. How many seeds would be needed to reach a target effect (default 0.02
   PR-AUC, which is about the size of difference this literature reports).
4. The resolution limit of the rank tests week 9 is likely to use. With 10
   pairs a two-sided sign test cannot reach p<0.05 without 9 of 10 wins, and
   Wilcoxon signed-rank bottoms out at p=0.002. Those are hard floors that no
   amount of effect size can move.

Read the MDE against the effect you would find interesting. If the MDE is
larger than any plausible quantum advantage, more seeds is the only honest fix,
and it is cheap on the classical side and expensive on the quantum side -- so
decide now, not in week 9.

Usage:
    PYTHONPATH=src python scripts/power_analysis.py --dataset churn --track matched
    PYTHONPATH=src python scripts/power_analysis.py --dataset fraud --track matched --target 0.02
    PYTHONPATH=src python scripts/power_analysis.py --all
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

KERNELS = ("linear", "rbf", "poly")
ALPHA = 0.05
POWER = 0.80
MAX_SEEDS = 500


def load(path):
    with open(path) as f:
        return [json.loads(line) for line in f]


def paired_differences(recs, metric="test_average_precision"):
    """Per-cell, per-kernel-pair, the list of per-seed differences.

    Pairing is on (mapping, n_qubits, seed): the same subsample, the same
    split, the same mapped features. Only the kernel differs. That is exactly
    the structure of the week-9 quantum-vs-classical comparison.
    """
    by_cell = defaultdict(dict)
    for r in recs:
        by_cell[(r["mapping"], r["n_qubits"], r["seed"])][r["method"]] = r[metric]

    out = defaultdict(lambda: defaultdict(list))
    cells = defaultdict(list)
    for (mapping, nq, seed), by_method in by_cell.items():
        cells[(mapping, nq)].append(seed)
        for a, b in itertools.combinations(KERNELS, 2):
            if a in by_method and b in by_method:
                out[(mapping, nq)][f"{a}-{b}"].append(by_method[a] - by_method[b])
    return out, cells


def mde_paired_t(sd, n, alpha=ALPHA, power=POWER):
    """Smallest true mean difference detectable with `power` at `alpha`.

    Exact: solves for the non-centrality parameter of the non-central t whose
    rejection probability equals `power`, then converts back to raw units.
    The familiar sd*(z_{1-a/2}+z_power)/sqrt(n) formula is the large-sample
    limit of this and is optimistic at n=10.
    """
    if n < 2 or sd <= 0 or not math.isfinite(sd):
        return float("nan")
    df = n - 1
    t_crit = stats.t.ppf(1 - alpha / 2, df)

    def achieved(nc):
        # Two-sided power; the lower tail is negligible but included for exactness.
        return (1 - stats.nct.cdf(t_crit, df, nc)) + stats.nct.cdf(-t_crit, df, nc)

    lo, hi = 0.0, 1.0
    while achieved(hi) < power and hi < 1e4:
        hi *= 2
    for _ in range(200):
        mid = (lo + hi) / 2
        if achieved(mid) < power:
            lo = mid
        else:
            hi = mid
    nc = (lo + hi) / 2
    return nc * sd / math.sqrt(n)


def seeds_for(sd, target, alpha=ALPHA, power=POWER):
    """Smallest n whose MDE is at or below `target`."""
    if sd <= 0 or target <= 0:
        return None
    for n in range(3, MAX_SEEDS + 1):
        if mde_paired_t(sd, n, alpha, power) <= target:
            return n
    return None


def rank_test_floor(n):
    """Best two-sided p the sign test and Wilcoxon can reach with n pairs."""
    sign_p = 2 * 0.5**n
    wins_needed = None
    for k in range(n, n // 2, -1):
        p = 2 * sum(math.comb(n, i) for i in range(k, n + 1)) / 2**n
        if p <= ALPHA:
            wins_needed = k
        else:
            break
    d = np.arange(1, n + 1, dtype=float)  # any all-positive set of differences
    wil_p = float(stats.wilcoxon(d, alternative="two-sided", method="exact").pvalue)
    return sign_p, wins_needed, wil_p


def report(path, target, metric):
    recs = load(path)
    diffs, cells = paired_differences(recs, metric=metric)
    n_seeds = max((len(set(v)) for v in cells.values()), default=0)

    print(f"=== {path.name}  ({metric}) ===")
    print(f"    {len(recs)} records, {len(cells)} cell{'s' if len(cells) != 1 else ''}, "
          f"{n_seeds} seeds per cell\n")

    print(f"    {'cell':<18}{'pair':<14}{'seeds':>7}{'mean diff':>11}{'paired sd':>11}"
          f"{'MDE':>10}{'n for ' + format(target, '.3f'):>14}")
    all_sd = []
    rows = []
    for (mapping, nq), by_pair in sorted(diffs.items(), key=lambda kv: (kv[0][0], kv[0][1] or 0)):
        q = "-" if nq is None else str(nq)
        for pair, ds in sorted(by_pair.items()):
            if len(ds) < 2:
                continue
            sd = st.stdev(ds)
            mean = st.mean(ds)
            n = len(ds)
            mde = mde_paired_t(sd, n)
            need = seeds_for(sd, target)
            all_sd.append(sd)
            rows.append({"mapping": mapping, "n_qubits": nq, "pair": pair, "n": n,
                         "mean_difference": mean, "paired_sd": sd, "mde": mde,
                         "seeds_for_target": need})
            print(f"    {mapping + '/' + q:<18}{pair:<14}{n:>7}{mean:>+11.4f}{sd:>11.4f}{mde:>10.4f}"
                  f"{(str(need) if need else '>' + str(MAX_SEEDS)):>14}")

    if not all_sd:
        print("    no paired differences found\n")
        return {"file": path.name, "rows": []}

    med = float(np.median(all_sd))
    worst = float(np.max(all_sd))
    print(f"\n    paired sd across all cells: median {med:.4f}, max {worst:.4f}")
    print(f"    MDE at n={n_seeds} seeds : {mde_paired_t(med, n_seeds):.4f} (median sd), "
          f"{mde_paired_t(worst, n_seeds):.4f} (worst cell)")
    need_med = seeds_for(med, target)
    print(f"    seeds to detect {target:.3f}  : {need_med if need_med else '>' + str(MAX_SEEDS)} "
          f"(median sd)")

    sign_p, wins, wil_p = rank_test_floor(n_seeds)
    print(f"\n    RANK-TEST FLOOR at {n_seeds} pairs (these do not improve with effect size):")
    if wins is None:
        print(f"      sign test     : CANNOT reach p<={ALPHA} at {n_seeds} pairs. Even a clean "
              f"sweep gives p={sign_p:.4f}.")
    else:
        print(f"      sign test     : best two-sided p = {sign_p:.4f}; "
              f"needs {wins}/{n_seeds} wins to reach p<={ALPHA}")
    if wil_p > ALPHA:
        print(f"      Wilcoxon      : CANNOT reach p<={ALPHA} at {n_seeds} pairs "
              f"(floor p = {wil_p:.4f}).")
    else:
        print(f"      Wilcoxon      : best two-sided p = {wil_p:.4f} (all differences same sign)")
    print()
    return {"file": path.name, "metric": metric, "n_seeds": n_seeds, "median_paired_sd": med,
            "max_paired_sd": worst, "mde_median_sd": mde_paired_t(med, n_seeds),
            "mde_worst_sd": mde_paired_t(worst, n_seeds), "target": target,
            "seeds_for_target_median_sd": need_med,
            "sign_test_floor_p": sign_p, "sign_test_wins_needed": wins,
            "wilcoxon_floor_p": wil_p, "rows": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset")
    ap.add_argument("--track", default="matched")
    ap.add_argument("--all", action="store_true", help="every non-shuffled file in the run directory")
    ap.add_argument("--target", type=float, default=0.02,
                    help="effect size you would want to detect, in metric units")
    ap.add_argument("--metric", default="test_average_precision")
    ap.add_argument("--in-dir", default=str(ROOT / "results" / "runs" / "classical"))
    ap.add_argument("--out", default=str(ROOT / "results" / "analysis" / "power.json"))
    args = ap.parse_args()

    in_dir = Path(args.in_dir)
    if args.all:
        paths = sorted(p for p in in_dir.glob("*.jsonl") if "_shuffled" not in p.name)
    else:
        if not args.dataset:
            ap.error("give --dataset or --all")
        # Glob rather than construct the name: since the training-size sweep a
        # matched run is <dataset>_matched_n<size>.jsonl, and the pre-23-Sep
        # archive is <dataset>_matched.jsonl. Both should be found.
        paths = sorted(p for p in in_dir.glob(f"{args.dataset}_{args.track}*.jsonl")
                       if "_shuffled" not in p.name)
        if not paths:
            ap.error(f"no files matching {args.dataset}_{args.track}*.jsonl in {in_dir}")

    print("Paired design: same subsample, same split, same mapping; only the kernel differs.")
    print(f"alpha={ALPHA} two-sided, power={POWER}, exact non-central t.\n")

    summaries = [report(p, args.target, args.metric) for p in paths if p.exists()]
    for p in paths:
        if not p.exists():
            print(f"missing: {p.name}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"alpha": ALPHA, "power": POWER, "target": args.target,
                               "metric": args.metric, "summaries": summaries}, indent=2) + "\n")
    print(f"-> {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    print("\nHow to read this: if the MDE is bigger than the advantage you would find")
    print("interesting, a null result from this design is uninformative. Fix it by adding")
    print("seeds or enlarging the test set, and decide that BEFORE the quantum runs.")


if __name__ == "__main__":
    main()
