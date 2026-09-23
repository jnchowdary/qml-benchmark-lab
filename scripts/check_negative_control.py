#!/usr/bin/env python3
"""Re-read a label-shuffled run and report the verdict against the correct null.

The control runs themselves do not need repeating -- the JSONL already holds
everything. This re-reads them with the corrected expectation from
qbench.metrics, so the 100 minutes of compute spent on 23 Sep 2026 is not
spent twice because the interpretation, not the experiment, was wrong.

Usage:
    PYTHONPATH=src python scripts/check_negative_control.py --all
    PYTHONPATH=src python scripts/check_negative_control.py --file results/runs/classical/churn_matched_n250_shuffled.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from run_classical_baselines import negative_control_verdict  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", nargs="*", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--in-dir", default=str(ROOT / "results" / "runs" / "classical"))
    args = ap.parse_args()

    paths = [Path(f) for f in args.file]
    if args.all or not paths:
        paths = sorted(Path(args.in_dir).glob("*_shuffled.jsonl"))
    if not paths:
        raise SystemExit(f"no *_shuffled.jsonl files in {args.in_dir}")

    for path in paths:
        recs = [json.loads(line) for line in path.open()]
        if not recs[0].get("shuffled"):
            print(f"{path.name}: NOT a shuffled run, skipping")
            continue
        print(f"\n{'=' * 78}\n{path.name}: {len(recs)} records")
        negative_control_verdict(recs)


if __name__ == "__main__":
    main()
