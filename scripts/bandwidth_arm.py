#!/usr/bin/env python3
"""Did widening the quantum grid buy signal, or buy noise?

THE QUESTION, AND WHY IT NEEDS A NULL
-------------------------------------
The registered quantum grid tunes no bandwidth. Adding one and finding that the
quantum arm improves proves nothing on its own, because **widening any grid
raises the best inner-CV score even when no searched point is genuinely
better**. On the classical grids that effect was measured: extending them in
both directions gained five to seven times more on shuffled labels than on real
ones, which is why those grids were left alone.

So the number that decides anything here is not the gain from widening. It is
the gain on real labels *relative to* the gain on permuted labels, where by
construction there is nothing to find. Pre-registration section 7 requires
exactly this, and docs/deviations.md D4 fixed the rule before the arm ran.

WHAT IS COMPARED
----------------
For each seed, in the primary cell: best-quantum-of-four from the registered
file, and best-quantum-of-four from the bandwidth file, both selected by inner
CV only. Their difference is the gain from widening, per seed, paired.

Then the same on the shuffled-label files. Seeds index the same subsample in
both, so the two gains are paired seed by seed and their difference is the
quantity of interest.

WHAT THIS SCRIPT WILL NOT DO
----------------------------
It does not test H1. It reports no confirmatory p-value. If the gain is real it
narrows what the registered H1 result is a result ABOUT, and that is an
interpretive change stated in prose in D4, not a new test.

Usage:
    PYTHONPATH=src python scripts/bandwidth_arm.py --dataset churn
    PYTHONPATH=src python scripts/bandwidth_arm.py --all
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from primary_tests import PRIMARY_CELL, best_by_inner, endpoint_test, fmt_p, norm_ap  # noqa: E402

ALPHA = 0.05


def load(path):
    if not path.exists():
        return None
    return [json.loads(l) for l in path.open() if l.strip()]


def by_cell_seed(recs, cell):
    out = defaultdict(list)
    for r in recs:
        if (r["mapping"], r["n_qubits"]) == cell:
            out[r["seed"]].append(r)
    return out


def gain(reg, wide, cell):
    """Per seed: normAP of the widened arm minus the registered arm.

    Both arms pick their own best setting by inner CV. That is the point: the
    question is what a practitioner who tuned bandwidth would have got, against
    what the registered grid got, each doing its own honest selection.
    """
    a, b = by_cell_seed(reg, cell), by_cell_seed(wide, cell)
    rows = []
    for seed in sorted(set(a) & set(b)):
        ra, rb = best_by_inner(a[seed]), best_by_inner(b[seed])
        if ra["test_label_fingerprint"] != rb["test_label_fingerprint"]:
            raise SystemExit(
                f"HALT: seed {seed} was scored on different test points in the "
                f"registered and bandwidth files. The two arms are not comparable.")
        rows.append({"seed": seed,
                     "reg": norm_ap(ra), "wide": norm_ap(rb),
                     "gain": norm_ap(rb) - norm_ap(ra),
                     "gain_roc": float(rb["test_roc_auc"]) - float(ra["test_roc_auc"]),
                     "bandwidth": rb.get("bandwidth"),
                     "reg_setting": ra["setting"], "wide_setting": rb["setting"]})
    return rows


def describe(label, rows):
    if not rows:
        print(f"    {label}: no paired seeds")
        return None
    e = endpoint_test([r["gain"] for r in rows])
    print(f"    {label}: mean gain {e['mean']:+.4f}  median {e['median']:+.4f}  "
          f"sd {e['sd']:.4f}  p {fmt_p(e['p_wilcoxon'])}  (n={e['n']})")
    return e


def report(dataset, n_per_class, q_dir, c_dir):
    cell = PRIMARY_CELL[dataset]
    tag = f"{dataset}_matched_n{n_per_class}"
    files = {"reg": q_dir / f"{tag}.jsonl",
             "wide": q_dir / f"{tag}_bw.jsonl",
             "reg_sh": q_dir / f"{tag}_shuffled.jsonl",
             "wide_sh": q_dir / f"{tag}_bw_shuffled.jsonl"}
    loaded = {k: load(v) for k, v in files.items()}
    missing = [files[k].name for k, v in loaded.items() if v is None]
    if missing:
        print(f"\n--- {dataset}, {n_per_class} per class: missing {', '.join(missing)}")
        if "reg_sh" in [k for k, v in loaded.items() if v is None] or \
           "wide_sh" in [k for k, v in loaded.items() if v is None]:
            print("    The shuffled arm is not optional. Without it the gain below "
                  "cannot be distinguished from winner's curse, and D4 forbids "
                  "reporting it alone.")
        return None

    print(f"\n{'=' * 74}")
    print(f"BANDWIDTH ARM (EXPLORATORY, deviations D4): {dataset}, "
          f"{cell[0]}/{cell[1]} qubits, {n_per_class} per class")
    print(f"{'=' * 74}")

    real = gain(loaded["reg"], loaded["wide"], cell)
    null = gain(loaded["reg_sh"], loaded["wide_sh"], cell)

    print("\n  Gain from adding a bandwidth grid, in normAP:")
    e_real = describe("real labels     ", real)
    e_null = describe("permuted labels ", null)
    if not (e_real and e_null):
        return None

    print("\n  The comparison that decides it:")
    ratio = (e_real["mean"] / e_null["mean"]) if abs(e_null["mean"]) > 1e-12 else float("inf")
    print(f"    real gain / permuted gain = {ratio:.2f}"
          f"   (the classical grids measured 0.14 to 0.20 here, which is why they "
          f"were left frozen)")

    paired = [r["gain"] for r in real]
    nullg = [dict((x["seed"], x["gain"]) for x in null).get(r["seed"]) for r in real]
    both = [(a, b) for a, b in zip(paired, nullg) if b is not None]
    if len(both) > 1:
        d = np.array([a - b for a, b in both])
        e = endpoint_test(list(d))
        print(f"    excess of real over permuted, paired by seed: {e['mean']:+.4f} "
              f"[{e['ci'][0]:+.4f}, {e['ci'][1]:+.4f}]  p {fmt_p(e['p_wilcoxon'])}")
    else:
        e = None

    chosen = Counter(r["bandwidth"] for r in real)
    print(f"\n  inner CV chose bandwidth (real labels): "
          f"{dict(sorted(chosen.items(), key=lambda kv: kv[0]))}")
    at_edge = sum(n for b, n in chosen.items() if b in (0.0625, 4.0))
    if at_edge:
        print(f"    {at_edge}/{len(real)} seeds selected a value on the grid boundary. "
              f"Per section 7 this is descriptive, not a licence to widen again.")
    if all(b == 1.0 for b in chosen):
        print("    Every seed chose the registered bandwidth: the registered grid was "
              "adequate at the registered scale, and D4's third outcome applies.")

    print(f"\n  absolute normAP in this cell: registered "
          f"{np.mean([r['reg'] for r in real]):.4f} -> widened "
          f"{np.mean([r['wide'] for r in real]):.4f}")

    verdict = _verdict(e_real, e_null, e, chosen)
    print(f"\n  READING, per D4: {verdict}")

    return {"dataset": dataset, "n_per_class": n_per_class, "cell": list(cell),
            "gain_real": e_real, "gain_permuted": e_null, "excess": e,
            "ratio": ratio, "bandwidths": {str(k): v for k, v in chosen.items()},
            "verdict": verdict, "confirmatory": False}


def _verdict(e_real, e_null, e_excess, chosen):
    """The three outcomes D4 fixed in advance, and nothing else."""
    if all(b == 1.0 for b in chosen):
        return ("the registered grid was adequate at the registered scale. D4 "
                "outcome three: the twelve-of-twelve reps ordering needs another "
                "explanation, which must be found rather than left open.")
    if e_real["mean"] <= 0:
        return ("widening did not help on real labels. The registered result stands "
                "unqualified. D4 outcome three.")
    if e_excess is None or e_excess["p_wilcoxon"] >= ALPHA or e_excess["mean"] <= 0:
        return ("widening gained no more on real labels than on permuted ones. This "
                "is winner's curse, the registered result stands unqualified, and "
                "this arm becomes a control that strengthens H1. D4 outcome two.")
    return ("widening gained materially more on real labels than on noise. The "
            "registered H1 rejection on churn is a result about FIXED-BANDWIDTH "
            "quantum kernels and the paper must say so in those words. H1 stands as "
            "computed; its scope narrows. D4 outcome one.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=sorted(PRIMARY_CELL))
    ap.add_argument("--n-per-class", type=int, default=250)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--quantum-dir", default=str(ROOT / "results" / "runs" / "quantum"))
    ap.add_argument("--classical-dir", default=str(ROOT / "results" / "runs" / "classical"))
    ap.add_argument("--out", default=str(ROOT / "results" / "analysis" / "bandwidth_arm.json"))
    args = ap.parse_args()

    print("Adding a hyperparameter always raises the best inner-CV score. The test is")
    print("whether it raises it MORE on real labels than on permuted ones.")
    print("This arm is exploratory (deviations D4) and produces no confirmatory result.")

    jobs = ([(d, args.n_per_class) for d in sorted(PRIMARY_CELL)] if args.all
            else [(args.dataset, args.n_per_class)])
    if not args.all and not args.dataset:
        ap.error("give --dataset or --all")

    out = [r for r in (report(d, n, Path(args.quantum_dir), Path(args.classical_dir))
                       for d, n in jobs) if r]
    if out:
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"exploratory": True, "deviation": "D4",
                                 "results": out}, indent=2, default=float) + "\n")
        print(f"\n-> {p.relative_to(ROOT) if p.is_relative_to(ROOT) else p}")


if __name__ == "__main__":
    main()
