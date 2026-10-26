#!/usr/bin/env python3
"""Prove that extracting the audit out of the research repository changed no answer.

WHY A SCRIPT AND NOT A README CLAIM
-----------------------------------
The assertion is that `qaudit` and `scripts/audit.py` give the same report on
the same input. That is checkable, so it is checked. The fixture is the one real
external case this tool has: Kakavand et al.'s hardware deposit, whose audit
report was committed to the research repository on 29 September 2026 at
`results/audits/kakavand_hw_report.json`. Every field of every check is
compared, not just the status, because a port that kept fourteen statuses and
changed a number inside one would pass a status comparison and be wrong.

TWO DIVERGENCES WERE FOUND. NEITHER WAS THE EXTRACTION.
-------------------------------------------------------
**First: --hook-sample.** The committed report reads `worst 4.5e+05 over 6
sampled kernels`; the first run of this check read `worst 1.7e+04 over 2 sampled
kernels`. The cause is the audit's own default of 6, which on this file reaches
two of the six deposited Grams, and 1.7e+04 is the reading section 5.6 of the
paper already documents as understating the worst case by a factor of 26. A
sample of 18 reproduces the committed report exactly.

The finding is that **the committed report does not record which sample
produced it.** It stores `file`, `control` and `floor`, and not `cell_fields`,
`hook` or `hook_sample` -- so the one knob that moves the only Tier 2
measurement in the paper by 26x is absent from the report carrying it, and the
default silently returns the understated reading. A report that cannot
reproduce itself is the gap this package closes in its own output.

**Second: the last digits of a condition number.** At sample 18 every status,
every detail string and every integer agreed, and two floats did not:

    cond_min   expected 10.565166570822727   got 10.565166570822726
    cond_max   expected 453631.34235576633   got 453631.34235548635

The cause is the floating-point environment, not the port. Measured in ONE
environment, three mathematically identical routes to HW-02's condition number
-- `np.linalg.cond`, the ratio of singular values, and the ratio of eigenvalue
magnitudes -- disagree by 4.62e-12 relative. The gap between this environment
and the committed value is 6.17e-13, which is smaller. The digits that diverged
were never determined by the measurement, and both readings print as 4.5e+05.

**Confirmed 25 October 2026, and it narrowed the cause.** On macOS arm64, the
platform that produced the committed report, this check passes with NO
tolerance -- every float bit for bit -- under numpy 2.5.4 and scipy 1.18.1,
where the committed report was produced under numpy 2.4.4 and scipy 1.17.1. Two
library versions on one platform agree exactly; one platform change does not.
The variable is the BLAS, not the library version.

**So the comparison is exact by default.** The earlier default of a 1e-9
tolerance was a workaround for the machine I was checking on, not a property of
the measurement, and a tolerance that exists to make one environment pass is
the kind of threshold this protocol is supposed to refuse. Pass `--rtol` to
compare across platforms, where it prints the tolerance and the largest
observed divergence rather than hiding either. **What a 1e-9 tolerance would
fail to catch:** a genuine change to a condition number smaller than one part
in a billion. The conditioning check's threshold is 1e12 against readings of
1e+01 to 1e+05, so a change at that resolution could not move a verdict -- but
that is an argument for the tolerance being safe when needed, not for it being
the default.

Usage, from the research repository root:
    KAKAVAND_DEPOSIT=... python product/qaudit/verify_extraction.py
    KAKAVAND_DEPOSIT=... python product/qaudit/verify_extraction.py --rtol 1e-9
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

FIXTURE  = "results/audits/kakavand_hw.jsonl"
EXPECTED = "results/audits/kakavand_hw_report.json"
HOOK     = "scripts/foreign/kakavand_adapter.py"

# The sample that reproduces the committed report. NOT the tool's default of 6,
# and the committed report does not say so. See the docstring.
REPRODUCING_SAMPLE = 18

# Exact by default: the platform that produced the committed report reproduces
# it bit for bit. --rtol is for comparing across platforms, where the BLAS
# differs; its justification and its blind spot are in the docstring.
CROSS_PLATFORM_RTOL = 1e-9

# Checks this package has added since the extraction. The committed report
# predates them, so their absence from it is expected and their presence is not
# a divergence. Declared by name: a check added WITHOUT being declared here is
# still a divergence, because a report silently growing a check is how a reader
# comes to believe a file answered a question nobody asked it.
CHECKS_ADDED_SINCE_EXTRACTION = {"hardware cost claims"}


def diff_numbers(e, g, rtol):
    """Compare two `numbers` dicts. Floats within rtol; everything else exact.

    Returns (divergences, largest_relative_float_gap).
    """
    bad, worst = [], 0.0
    if type(e) is not type(g) or not isinstance(e, dict):
        return ([f"numbers shape differs: {e!r} against {g!r}"] if e != g else []), 0.0
    if set(e) != set(g):
        bad.append(f"numbers keys differ: {sorted(set(e) ^ set(g))}")
    for k in sorted(set(e) & set(g)):
        a, b = e[k], g[k]
        if isinstance(a, float) and isinstance(b, float):
            if a == b:
                continue
            scale = max(abs(a), abs(b))
            rel = abs(a - b) / scale if scale else abs(a - b)
            worst = max(worst, rel)
            if not (math.isfinite(a) and math.isfinite(b)) or rel > rtol:
                bad.append(f"numbers.{k}: expected {a!r}, got {b!r} "
                           f"(relative {rel:.2e}, tolerance {rtol:.0e})")
        elif a != b:
            bad.append(f"numbers.{k}: expected {a!r}, got {b!r}")
    return bad, worst


def compare(expected, got, rtol):
    bad, worst = [], 0.0
    for key in ("file", "control", "floor"):
        if expected.get(key) != got.get(key):
            bad.append(f"top-level {key}: expected {expected.get(key)!r}, got {got.get(key)!r}")

    e_checks = {c["name"]: c for c in expected.get("checks", [])}
    g_checks = {c["name"]: c for c in got.get("checks", [])}
    only_e = sorted(set(e_checks) - set(g_checks))
    added = set(g_checks) - set(e_checks)
    if only_e:
        bad.append(f"checks MISSING from the new report: {only_e}")
    undeclared = sorted(added - CHECKS_ADDED_SINCE_EXTRACTION)
    if undeclared:
        bad.append(f"checks the new report added WITHOUT declaring them in "
                   f"CHECKS_ADDED_SINCE_EXTRACTION: {undeclared}")
    missing_declared = sorted(CHECKS_ADDED_SINCE_EXTRACTION - added)
    if missing_declared:
        bad.append(f"declared as added but not present in the new report: {missing_declared}")

    for name in sorted(set(e_checks) & set(g_checks)):
        e, g = e_checks[name], g_checks[name]
        for field in ("status", "tier", "detail"):
            if e.get(field) != g.get(field):
                bad.append(f"{name}.{field}:\n        expected: {e.get(field)!r}\n        got:      {g.get(field)!r}")
        nb, nw = diff_numbers(e.get("numbers"), g.get("numbers"), rtol)
        worst = max(worst, nw)
        bad += [f"{name}.{b}" for b in nb]

    e_nr = {(n["name"], n["reason"]) for n in expected.get("not_runnable", [])}
    g_nr = {(n["name"], n["reason"]) for n in got.get("not_runnable", [])}
    if e_nr != g_nr:
        bad.append(f"not_runnable differs:\n        expected: {sorted(e_nr)}\n        got:      {sorted(g_nr)}")
    return bad, worst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--deposit", default=os.environ.get("KAKAVAND_DEPOSIT"))
    ap.add_argument("--hook-sample", type=int, default=REPRODUCING_SAMPLE)
    ap.add_argument("--rtol", type=float, nargs="?", const=CROSS_PLATFORM_RTOL,
                    default=0.0, metavar="REL",
                    help=f"compare floats within this relative tolerance instead of "
                         f"exactly, for comparing a report across platforms, where the "
                         f"BLAS differs. Bare --rtol uses {CROSS_PLATFORM_RTOL:.0e}.")
    a = ap.parse_args()
    rtol = a.rtol

    repo = Path(a.repo).resolve()
    for rel in (FIXTURE, EXPECTED, HOOK):
        if not (repo / rel).exists():
            raise SystemExit(f"\n  {rel} is not in {repo}. Run this from the research repository root.\n")
    if not a.deposit:
        raise SystemExit("\n  set KAKAVAND_DEPOSIT or pass --deposit: the hook needs the deposit's six\n"
                         "  K_hardware.npz arrays, which this repository does not redistribute.\n")

    expected = json.loads((repo / EXPECTED).read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "report.json"
        env = dict(os.environ, KAKAVAND_DEPOSIT=str(a.deposit))
        proc = subprocess.run(
            [sys.executable, "-m", "qaudit.audit", FIXTURE, "--hook", HOOK,
             "--hook-sample", str(a.hook_sample), "--json", str(out)],
            cwd=repo, env=env, capture_output=True, text=True)
        if not out.exists():
            raise SystemExit(f"\n  qaudit wrote no report (exit {proc.returncode}):\n{proc.stderr[-2000:]}\n")
        got = json.loads(out.read_text(encoding="utf-8"))
        exit_code = proc.returncode

    import numpy, scipy, qaudit
    n = len(expected.get("checks", []))
    print(f"\nEXTRACTION CHECK")
    print(f"  fixture        {FIXTURE}")
    print(f"  expected       {EXPECTED}  (committed 29 September 2026)")
    print(f"  tool           qaudit {qaudit.__version__}, numpy {numpy.__version__}, scipy {scipy.__version__}")
    print(f"  --hook-sample  {a.hook_sample}"
          f"{'' if a.hook_sample == REPRODUCING_SAMPLE else '  (NOT the reproducing sample)'}")
    print(f"  float compare  {'EXACT, no tolerance' if not rtol else f'relative tolerance {rtol:.0e}'}\n")

    added = sorted({c["name"] for c in got["checks"]} - {c["name"] for c in expected["checks"]})
    if added:
        print(f"  added since    {', '.join(added)}  (declared)\n")

    bad, worst = compare(expected, got, rtol)
    if bad:
        print(f"  {len(bad)} divergence(s) across {n} checks:\n")
        for b in bad:
            print(f"    - {b}")
        print("\n  A divergence is a finding. Investigate the cause before changing either\n"
              "  the implementation or the expected report.\n")
        raise SystemExit(1)

    states = {}
    for c in got["checks"]:
        states[c["status"]] = states.get(c["status"], 0) + 1
    print(f"  all {n} checks in the committed report agree with it: name, status, tier, detail")
    print(f"  and numbers on each, plus the not-runnable list and file, control, floor.")
    if worst:
        print(f"\n  largest float divergence observed: {worst:.2e} relative, against a")
        print(f"  tolerance of {rtol:.0e} and a within-environment spread of 4.62e-12")
        print(f"  between three identical routes to the same condition number.")
    else:
        print(f"\n  every float matched bit for bit"
              f"{', with no tolerance allowed' if not rtol else ''}.")
    print(f"\n  report shape: " + ", ".join(f"{v} {k}" for k, v in sorted(states.items())))
    print(f"  exit code {exit_code}, which is what a FAIL should give\n")
    print("  The extraction changed no answer.\n")


if __name__ == "__main__":
    main()
