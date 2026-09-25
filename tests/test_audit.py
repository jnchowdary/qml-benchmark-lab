"""The audit protocol: every check, on fixtures that make it fire.

WHY THIS FILE EXISTS
--------------------
`scripts/audit.py` is the only artefact in this project intended for anyone
else to run. Every other script answers a question about churn and fraud; this
one makes a claim about somebody's pipeline. A check that silently passes on a
broken file is worse than no check, because it launders the defect.

So each check is tested twice: once on input it must clear, and once on input
it must catch. The degraded path matters as much as the happy one, because a
foreign pipeline will not emit the recommended fields and the audit has to say
which questions it therefore cannot answer rather than quietly answering fewer.
"""

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import audit  # noqa: E402


def rec(seed=0, method="rbf", ap=0.70, roc=0.70, n_test=150, base=0.5,
        mapping="pca", nq=12, **kw):
    r = {"method": method, "seed": seed, "n_train": 350, "n_test": n_test,
         "test_base_rate": base, "test_average_precision": ap, "test_roc_auc": roc,
         "test_label_fingerprint": hashlib.sha256(str(seed).encode()).hexdigest()[:16],
         "shuffled": False, "final_converged": True, "inner_score": 0.6,
         "cell": {"mapping": mapping, "n_qubits": nq}}
    r.update(kw)
    return r


def paired(n_seeds=20, delta=0.05, **kw):
    out = []
    for s in range(n_seeds):
        jitter = 0.01 * ((s % 5) - 2)
        out.append(rec(seed=s, method="rbf", ap=0.70 + jitter, **kw))
        out.append(rec(seed=s, method="quantum", ap=0.70 + delta + jitter, **kw))
    return out


CTX = {"control": None, "floor": audit.DEFAULT_PRECISION_FLOOR}


def ctx(**kw):
    return {**CTX, **kw}


# ------------------------------------------------------------------ schema

def test_schema_fails_without_required_fields():
    bad = [{k: v for k, v in rec().items() if k != "test_roc_auc"}]
    o = audit.check_schema(bad, ctx())
    assert o.status == audit.FAIL
    assert "test_roc_auc" in o.detail


def test_schema_warns_but_proceeds_without_recommended_fields():
    mini = [{k: rec()[k] for k in ("method", "seed", "n_train", "n_test",
                                   "test_base_rate", "test_average_precision",
                                   "test_roc_auc")}]
    o = audit.check_schema(mini, ctx())
    assert o.status == audit.WARN
    assert "skip" in o.detail


def test_schema_passes_on_a_complete_record():
    assert audit.check_schema([rec()], ctx()).status == audit.PASS


# --------------------------------------------------------- chance correction

def test_chance_ap_exceeds_the_base_rate_and_is_reported():
    o = audit.check_chance_correction([rec()], ctx())
    assert o.status == audit.PASS
    assert o.numbers["chance_ap"] > o.numbers["base_rate"]


def test_mixed_test_set_shapes_are_flagged():
    """Two test-set sizes mean two different null levels, so raw AP is not
    comparable across them. This is the error that made a clean pipeline read
    as a 2.2-sigma leak in week 3."""
    o = audit.check_chance_correction([rec(n_test=150), rec(n_test=30)], ctx())
    assert o.status == audit.WARN
    assert o.numbers["chance_spread"] > 0


# ------------------------------------------------------------ control, pairing

def test_control_absent_is_a_skip_not_a_pass():
    o = audit.check_negative_control(paired(), ctx())
    assert o.status == audit.SKIP


def test_clean_control_passes():
    ctrl = [rec(seed=s, ap=0.5154, roc=0.50 + 0.004 * ((s % 5) - 2), shuffled=True)
            for s in range(20)]
    assert audit.check_negative_control(paired(), ctx(control=ctrl)).status == audit.PASS


def test_leaking_control_fails():
    ctrl = [rec(seed=s, ap=0.62, roc=0.60 + 0.004 * ((s % 5) - 2), shuffled=True)
            for s in range(20)]
    o = audit.check_negative_control(paired(), ctx(control=ctrl))
    assert o.status == audit.FAIL
    assert "sigma" in o.detail


def test_fingerprint_mismatch_fails():
    recs = paired()
    recs[3]["test_label_fingerprint"] = "deadbeefdeadbeef"
    assert audit.check_pairing(recs, ctx()).status == audit.FAIL


def test_missing_fingerprint_skips_and_says_why():
    recs = [{k: v for k, v in r.items() if k != "test_label_fingerprint"}
            for r in paired()]
    o = audit.check_pairing(recs, ctx())
    assert o.status == audit.SKIP
    assert "assumed" in o.detail


# ------------------------------------------------------------------- solver

def test_non_converged_fit_fails():
    recs = paired()
    recs[0]["final_converged"] = False
    assert audit.check_convergence(recs, ctx()).status == audit.FAIL


# --------------------------------------------------------- unit of analysis

def test_unit_of_analysis_reports_cells_not_records():
    recs = [r for nq in (4, 8, 12) for r in paired(mapping="pca", nq=nq)]
    o = audit.check_unit_of_analysis(recs, ctx())
    assert o.numbers["n_cells"] == 3
    assert o.numbers["n_records"] == 120
    assert "not" in o.detail


def test_unit_of_analysis_skips_with_one_configuration():
    assert audit.check_unit_of_analysis(paired(), ctx()).status == audit.SKIP


def test_absent_cell_field_groups_into_one_cell_not_one_per_method():
    """The fallback must not put each method in its own configuration; if it
    did, nothing would pair and the audit would report no comparisons on a file
    full of them."""
    recs = [{k: v for k, v in r.items() if k != "cell"} for r in paired()]
    assert len({audit.cell_of(r) for r in recs}) == 1
    assert audit.check_power(recs, ctx()).status in (audit.PASS, audit.WARN)


# ----------------------------------------------------------- power and floor

def test_power_reports_an_mde_and_the_exclusion_reading():
    o = audit.check_power(paired(), ctx())
    assert o.numbers["mde"] > 0
    assert "excludes effects LARGER" in o.detail


def test_power_skips_with_a_single_method():
    single = [rec(seed=s) for s in range(20)]
    assert audit.check_power(single, ctx()).status == audit.SKIP


def test_difference_below_the_floor_is_warned():
    o = audit.check_precision_floor(paired(delta=1e-5), ctx())
    assert o.status == audit.WARN
    assert o.numbers["below_floor"] == 1


def test_difference_above_the_floor_passes():
    assert audit.check_precision_floor(paired(delta=0.05), ctx()).status == audit.PASS


# ------------------------------------------------------------- multiplicity

def test_multiplicity_counts_comparisons_across_configurations():
    recs = [r for nq in (4, 8, 12) for r in paired(nq=nq)]
    o = audit.check_multiplicity(recs, ctx())
    assert o.status == audit.WARN
    assert o.numbers["comparisons"] == 3


def test_single_comparison_passes():
    assert audit.check_multiplicity(paired(), ctx()).status == audit.PASS


# ---------------------------------------------------------------- selection

def test_selection_skips_without_inner_scores():
    recs = [{k: v for k, v in r.items() if k != "inner_score"} for r in paired()]
    o = audit.check_selection_leak(recs, ctx())
    assert o.status == audit.SKIP
    assert "training folds" in o.detail


# ------------------------------------------------------- the runner contract

def test_every_check_returns_an_outcome_on_a_minimal_file(tmp_path):
    p = tmp_path / "m.jsonl"
    p.write_text("".join(json.dumps(
        {k: r[k] for k in ("method", "seed", "n_train", "n_test", "test_base_rate",
                           "test_average_precision", "test_roc_auc")}) + "\n"
        for r in paired()))
    _, outs = audit.run(str(p), None, audit.DEFAULT_PRECISION_FLOOR)
    assert len(outs) == len(audit.CHECKS)
    assert all(o.status in (audit.PASS, audit.WARN, audit.FAIL, audit.SKIP) for o in outs)


def test_a_check_that_raises_is_reported_as_a_failure(tmp_path, monkeypatch):
    """A broken check must never be silently absent from the report."""
    def boom(recs, ctx):
        raise RuntimeError("boom")
    monkeypatch.setattr(audit, "CHECKS", [boom])
    p = tmp_path / "x.jsonl"
    p.write_text(json.dumps(rec()) + "\n")
    _, outs = audit.run(str(p), None, audit.DEFAULT_PRECISION_FLOOR)
    assert outs[0].status == audit.FAIL and "boom" in outs[0].detail


def test_tier2_checks_are_listed_as_not_runnable_with_reasons():
    """Claiming a check ran when it could not is the error this tool exists to
    catch, so the non-portable ones are named and explained rather than hidden."""
    assert len(audit.TIER2) >= 4
    assert all(len(reason) > 40 for _, reason in audit.TIER2)
    assert any("bandwidth" in name for name, _ in audit.TIER2)


def test_a_degenerate_control_does_not_explode_into_a_false_failure():
    """Records with near-identical metrics give a standard error of order 1e-22,
    which is floating-point residue, not a measured spread. Dividing by it turned
    a deviation of 0.000014 into 3.5e16 sigma when this check was first written.
    Effect size and significance are both required, which is the same rule the
    surrogate verdict needed and for the same reason."""
    # 0.5154 rather than the exact chance value: identical-but-not-exact records
    # leave a standard error of ~1e-22 instead of a clean zero, which is the case
    # that actually exploded. An exact match gives se = 0 and sigma = 0 and would
    # not exercise the guard at all.
    ctrl = [rec(seed=s, ap=0.5154, roc=0.5, shuffled=True) for s in range(20)]
    o = audit.check_negative_control(paired(), ctx(control=ctrl))
    assert o.status == audit.PASS
    assert abs(o.numbers["normAP"]["sigma"]) > 1e6      # the sigma really is absurd
    assert abs(o.numbers["normAP"]["mean"]) < audit.DEFAULT_PRECISION_FLOOR


def test_a_real_leak_still_fails_after_the_guard():
    """The guard must not make the check toothless: a genuine leak clears both
    the sigma bar and the floor."""
    ctrl = [rec(seed=s, ap=0.62, roc=0.60 + 0.004 * ((s % 5) - 2), shuffled=True)
            for s in range(20)]
    assert audit.check_negative_control(paired(), ctx(control=ctrl)).status == audit.FAIL
