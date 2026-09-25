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


CTX = {"control": None, "floor": audit.DEFAULT_PRECISION_FLOOR,
       "cell_fields": None, "compare": None, "compare_fields": None}


def ctx(**kw):
    """Default context; pass cell_fields=... to group by configuration."""
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


# ------------------- configuration inference, from the failure that caused it

def qbench_shaped(n_seeds=20):
    """Records shaped like this project's own output: mapping and n_qubits at the
    top level, no nested 'cell' dict, plus provenance and cost telemetry."""
    return [{"dataset": "churn", "git_commit": "0b796a3", "track": "matched",
             "method": f"quantum-{st}", "setting": st, "embedding": st.split("-")[0],
             "reps": int(st[-1]), "mapping": mp, "n_qubits": q, "seed": s,
             "test_label_fingerprint": hashlib.sha256(str(s).encode()).hexdigest()[:16],
             "n_train": 350, "n_test": 150, "test_base_rate": 0.5,
             "test_average_precision": 0.70 + 0.01 * (s % 5),
             "test_roc_auc": 0.70, "n_per_class": 250, "shuffled": False,
             "device": "lightning.qubit",
             "circuit_evaluations": 113575 if s % 2 else 0,
             "simulator_executions": 500, "cache_hits": 3,
             "inner_score": 0.6, "final_converged": True}
            for mp in ("pca", "selectk", "randproj") for q in (4, 6, 8, 10, 12)
            for s in range(n_seeds) for st in ("angle-r1", "angle-r2", "iqp-r1", "iqp-r2")]


def test_configuration_is_inferred_without_a_nested_cell_field():
    """The bug this catches: the first version of the audit required a nested
    'cell' dict. Run against this project's own results it found none, collapsed
    fifteen configurations into one, skipped the unit-of-analysis check written
    for exactly that case, understated multiplicity fifteenfold, and pooled
    between-cell variance into the paired sd."""
    recs = qbench_shaped()
    assert audit.infer_cell_fields(recs) == ["mapping", "n_qubits"]
    fields = audit.infer_cell_fields(recs)
    assert len({audit.cell_of(r, fields) for r in recs}) == 15


def test_inference_rejects_fields_that_track_the_method():
    """embedding and reps vary, but each of their values is scored by only some
    of the methods, so they are arms of the comparison and not configurations."""
    fields = audit.infer_cell_fields(qbench_shaped())
    for f in ("embedding", "reps", "setting", "method"):
        assert f not in fields


def test_inference_rejects_cost_telemetry():
    """circuit_evaluations takes two values here, each scored by every method,
    so the co-occurrence rule alone would accept it and silently double the
    cell count. It is excluded by name."""
    assert "circuit_evaluations" not in audit.infer_cell_fields(qbench_shaped())
    assert "circuit_evaluations" in audit.NEVER_CELL


def test_multiplicity_counts_all_cells_once_configuration_is_inferred():
    recs = qbench_shaped()
    ctx_ = ctx(cell_fields=audit.infer_cell_fields(recs))
    o = audit.check_multiplicity(recs, ctx_)
    assert o.numbers["comparisons"] == 90          # 15 cells x 6 method pairs


def test_unit_of_analysis_fires_once_configuration_is_inferred():
    recs = qbench_shaped()
    o = audit.check_unit_of_analysis(recs, ctx(cell_fields=audit.infer_cell_fields(recs)))
    assert o.status == audit.WARN
    assert o.numbers["n_cells"] == 15 and o.numbers["n_records"] == 1200


def test_explicit_cell_fields_override_the_inference():
    recs = qbench_shaped()
    assert len({audit.cell_of(r, ["mapping"]) for r in recs}) == 3


def test_single_method_file_infers_nothing():
    """With one method there is no comparison, so nothing distinguishes a
    configuration field from any other varying field."""
    recs = [r for r in qbench_shaped() if r["method"] == "quantum-angle-r1"]
    assert audit.infer_cell_fields(recs) == []


# ----------------------------------------- the comparison that spans two arms

def classical_arm(q):
    """A second arm on the same splits and configurations."""
    out = []
    for r in q:
        if r["method"] != "quantum-angle-r1":
            continue
        for k in ("linear", "rbf", "poly"):
            x = dict(r)
            x["method"] = k
            x["setting"] = k
            x["test_average_precision"] = 0.72 + 0.008 * (x["seed"] % 5)
            out.append(x)
    return out


def cross_ctx(q, c):
    return ctx(cell_fields=audit.infer_cell_fields(q), compare=c,
               compare_fields=audit.infer_cell_fields(c))


def test_one_arm_alone_is_a_skip_that_says_the_figures_are_within_arm():
    """The finding this encodes: handed only the quantum file, the audit reported
    a minimum detectable effect of 0.0555 measured between quantum settings, while
    the comparison actually being tested was quantum against classical at 0.0171.
    Both were right about different pairs; reporting only the first describes the
    power of a comparison nobody is making."""
    o = audit.check_cross_arm(qbench_shaped(), ctx(cell_fields=["mapping", "n_qubits"]))
    assert o.status == audit.SKIP
    assert "WITHIN this file" in o.detail


def test_cross_arm_n_is_seeds_per_configuration_not_records():
    """Pooling all configurations into one bucket made n the record count. The
    first version of this very check reported n = 300 on 20 seeds, which is the
    fourth instance in this project of that mistake and the first committed
    inside the check written to explain it."""
    q = qbench_shaped(n_seeds=20)
    o = audit.check_cross_arm(q, cross_ctx(q, classical_arm(q)))
    assert o.status == audit.PASS
    assert "verified matching test points" in o.detail
    assert o.numbers["n_seeds"] == 20
    assert o.numbers["paired_groups"] == 300          # 15 configurations x 20 seeds


def test_cross_arm_fails_when_the_arms_were_scored_on_different_points():
    q = qbench_shaped()
    c = classical_arm(q)
    for r in c[:10]:
        r["test_label_fingerprint"] = "deadbeefdeadbeef"
    o = audit.check_cross_arm(q, cross_ctx(q, c))
    assert o.status == audit.FAIL
    assert "DIFFERENT test points" in o.detail


def test_cross_arm_fails_when_nothing_pairs():
    q = qbench_shaped()
    c = [dict(r, seed=r["seed"] + 1000) for r in classical_arm(q)]
    assert audit.check_cross_arm(q, cross_ctx(q, c)).status == audit.FAIL


def test_cross_arm_will_not_claim_pairing_it_cannot_verify():
    """Without fingerprints the arms are assumed to share test points. The first
    version printed "on matching test points" regardless, which is a claimed
    verification that never happened: the failure this tool exists to catch."""
    q = [{k: v for k, v in r.items() if k != "test_label_fingerprint"}
         for r in qbench_shaped()]
    c = [{k: v for k, v in r.items() if k != "test_label_fingerprint"}
         for r in classical_arm(qbench_shaped())]
    o = audit.check_cross_arm(q, cross_ctx(q, c))
    assert o.status == audit.WARN
    assert "ASSUMED and not verified" in o.detail


def test_unbalanced_telemetry_is_not_a_configuration():
    """On churn at 100 per class, n_nonconverged varied and every one of its
    values was scored by every method, so the co-occurrence rule alone accepted
    it. That gave 20 configurations instead of 15, ragged 367-group pairing, and
    a cross-arm failure because the classical arm inferred a different field set.

    A configuration is a designed grid and its values appear in roughly equal
    numbers. Telemetry does not. That is the discriminator."""
    recs = qbench_shaped()
    for i, r in enumerate(recs):
        r["n_nonconverged"] = 0 if i % 40 else 3        # 39:1, wildly unbalanced
    fields = audit.infer_cell_fields(recs)
    assert fields == ["mapping", "n_qubits"]
    assert len({audit.cell_of(r, fields) for r in recs}) == 15


def test_a_balanced_field_is_still_accepted_as_a_configuration():
    """The balance rule must not reject a genuine configuration. A training-size
    sweep inside one file is balanced and is a configuration."""
    recs = []
    for n in (50, 100, 250):
        for r in qbench_shaped(n_seeds=4):
            recs.append(dict(r, n_per_class=n))
    assert "n_per_class" in audit.infer_cell_fields(recs)


def test_both_arms_are_grouped_by_the_same_fields(tmp_path):
    """If each file infers its own fields the tuples have different shapes, no
    cell ever matches, and the cross-arm check fails in a way that reads like a
    data problem rather than a tooling one."""
    import json
    q = qbench_shaped(n_seeds=5)
    for i, r in enumerate(q):
        r["n_nonconverged"] = 0 if i % 40 else 3
    c = classical_arm(qbench_shaped(n_seeds=5))
    qp, cp = tmp_path / "q.jsonl", tmp_path / "c.jsonl"
    qp.write_text("".join(json.dumps(r) + "\n" for r in q))
    cp.write_text("".join(json.dumps(r) + "\n" for r in c))
    fields, outs = audit.run(str(qp), None, audit.DEFAULT_PRECISION_FLOOR,
                             None, str(cp))
    assert fields == ["mapping", "n_qubits"]
    cross = [o for o in outs if o.name == "cross-arm comparison"][0]
    assert cross.status == audit.PASS
