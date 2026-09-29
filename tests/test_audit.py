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

import numpy as np
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


def test_unit_of_analysis_does_not_skip_a_one_configuration_comparison():
    """This test previously asserted a SKIP, which was asserting the defect.

    One configuration does not mean no independent units; it means the split is
    the unit. `paired()` is 20 splits scored by two methods, so the answer is 20
    and never 40, and the check has to say so.
    """
    o = audit.check_unit_of_analysis(paired(), ctx())
    assert o.status == audit.WARN
    assert o.numbers["n_seeds"] == 20 and o.numbers["n_records"] == 40


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
    # NOT_RUN is a legitimate outcome now that hook-based checks live in CHECKS:
    # without a --hook they report what they could not reach, which is the whole
    # point of them being there rather than hidden in a static list.
    assert all(o.status in (audit.PASS, audit.WARN, audit.FAIL, audit.SKIP,
                            audit.NOT_RUN) for o in outs)


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
    assert len(audit.TIER2) >= 1
    assert all(len(reason) > 40 for _, reason in audit.TIER2)
    # Every remaining entry says what would make it runnable, so the list is a
    # route rather than an excuse.
    assert all("needs" in reason for _, reason in audit.TIER2)


def test_three_checks_left_tier2_and_none_quietly_vanished():
    """Week 5 moved three checks out of the unrunnable list, and a check that is
    no longer advertised as unrunnable must actually be running instead. This
    pins that: it is the exact shape of failure the tool exists to catch, and
    there is no reason to think the tool is exempt from it."""
    names = [n for n, _ in audit.TIER2]
    assert not any("bandwidth" in n for n in names)
    assert not any("conditioning" in n for n in names)
    assert not any("surrogate" in n for n in names)
    running = {o.name for o in
               (c(paired(n_seeds=4), ctx()) for c in audit.CHECKS)}
    assert "tuning symmetry" in running        # Tier 1, needs nothing
    assert "kernel conditioning" in running    # Tier 2, reports NOT_RUN unaided
    assert "classical surrogate equivalence" in running


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


# ----------------------------------------------------- tuning symmetry (Tier 1)

def tuned(method, values, key, n=6):
    """Records whose selected parameter takes `values` in rotation."""
    return [rec(seed=s, method=method, params={key: values[s % len(values)]},
                C=[0.1, 1.0, 10.0][s % 3]) for s in range(n)]


def test_tuning_symmetry_catches_one_arm_with_nothing_to_tune():
    """The defect that cost this project four weeks, now visible from records.

    The registered grid gave the classical arm eleven RBF bandwidths and the
    quantum arm a fixed data scale. A method that never varies its selection had
    nothing to select from, and the comparison then measures tuning.
    """
    quantum = [rec(seed=s, method="quantum-iqp-r1",
                   params={"embedding": "iqp", "reps": 1}, C=1.0) for s in range(6)]
    classical = tuned("rbf", [1e-3, 1e-2, 1e-1, 1.0], "gamma")
    o = audit.check_tuning_symmetry(quantum, ctx(compare=classical))
    assert o.status == audit.WARN
    assert "quantum-iqp-r1" in o.detail
    assert o.numbers["per_method"]["rbf"]["structural"] == 4
    assert o.numbers["per_method"]["quantum-iqp-r1"]["structural"] == 1


def test_tuning_symmetry_passes_when_both_arms_search():
    q = tuned("quantum", [0.25, 0.5, 1.0, 2.0], "bandwidth")
    c = tuned("rbf", [1e-3, 1e-2, 1e-1, 1.0], "gamma")
    o = audit.check_tuning_symmetry(q, ctx(compare=c))
    assert o.status == audit.PASS


def test_tuning_symmetry_skips_without_selected_parameters():
    """A pipeline that does not record what it selected makes the question
    unanswerable, and the check must say so rather than assume symmetry."""
    o = audit.check_tuning_symmetry(paired(n_seeds=4), ctx())
    assert o.status == audit.SKIP
    assert "params" in o.detail


def test_tuning_symmetry_is_not_fooled_by_a_constant_winner():
    """A wide grid whose best value never changes looks identical to no grid.
    The check must warn without claiming to know which it saw."""
    quantum = [rec(seed=s, method="quantum", params={"bandwidth": 1.0}, C=1.0)
               for s in range(6)]
    o = audit.check_tuning_symmetry(
        quantum, ctx(compare=tuned("rbf", [1e-3, 1e-2, 1e-1], "gamma")))
    assert o.status == audit.WARN
    assert "cannot tell them apart" in o.detail


# ------------------------------------------------------------- the Tier 2 hook

class FakeHook:
    """A hook standing in for a pipeline, so Tier 2 is tested without datasets."""

    def __init__(self, cond=1e3, surrogate_gap=0.20, split_drift=False):
        self.cond, self.gap, self.drift = cond, surrogate_gap, split_drift
        self.gaps, self._i = None, 0
        rng = np.random.default_rng(0)
        self.X = rng.normal(size=(24, 3))

    def gram(self, record):
        sq = np.sum((self.X[:, None, :] - self.X[None, :, :]) ** 2, axis=-1)
        K = np.exp(-0.5 * sq)
        # push the spectrum to the requested conditioning
        w, V = np.linalg.eigh(K)
        w = np.linspace(1.0, 1.0 / self.cond, len(w))
        return V @ np.diag(w) @ V.T

    def training_data(self, record):
        return self.X, np.array([0, 1] * 12)

    def refit(self, record, gamma):
        if self.drift:
            raise RuntimeError("hook rebuilt a different split than record seed=0")
        g = self.gap
        if self.gaps:
            g, self._i = self.gaps[self._i % len(self.gaps)], self._i + 1
        return {**rec(), "test_average_precision":
                record["test_average_precision"] - g}


def test_conditioning_not_run_without_a_hook_and_names_the_function():
    o = audit.check_conditioning(paired(n_seeds=4), ctx())
    assert o.status == audit.NOT_RUN
    assert "gram(record)" in o.detail


def test_conditioning_warns_on_an_underdetermined_dual():
    o = audit.check_conditioning(paired(n_seeds=4), ctx(hook=FakeHook(cond=1e15)))
    assert o.status == audit.WARN
    assert o.numbers["cond_max"] > 1e12
    assert "McNemar" in o.detail


def test_conditioning_passes_on_a_well_determined_kernel():
    o = audit.check_conditioning(paired(n_seeds=4), ctx(hook=FakeHook(cond=1e3)))
    assert o.status == audit.PASS


def test_surrogate_warns_when_the_kernel_is_its_own_surrogate():
    """A difference below the reproducibility floor is not a small effect. It is
    the kernel being a Gaussian kernel computed expensively."""
    o = audit.check_surrogate(paired(n_seeds=4), ctx(hook=FakeHook(surrogate_gap=0.0)))
    assert o.status == audit.WARN
    assert "classical-versus-classical" in o.detail


def test_surrogate_passes_when_the_kernel_separates():
    o = audit.check_surrogate(paired(n_seeds=4), ctx(hook=FakeHook(surrogate_gap=0.20)))
    assert o.status == audit.PASS
    assert "carries no sign about the best classical kernel" in o.detail


def test_surrogate_fails_loudly_when_the_hook_rebuilds_a_different_split():
    """The one way a hook does real damage: auditing a kernel the experiment
    never used. It must stop, not report a number."""
    o = audit.check_surrogate(paired(n_seeds=4), ctx(hook=FakeHook(split_drift=True)))
    assert o.status == audit.FAIL
    assert "nothing computed from it is comparable" in o.detail


def test_surrogate_not_run_names_every_missing_hook_function():
    class Partial:
        def gram(self, record):
            return np.eye(4)
    o = audit.check_surrogate(paired(n_seeds=4), ctx(hook=Partial()))
    assert o.status == audit.NOT_RUN
    assert "training_data" in o.detail and "refit" in o.detail
    assert "gram" not in o.detail.split("in --hook")[0].replace("training_data", "")


def test_hook_loading_is_optional_and_returns_none():
    assert audit.load_hook(None) is None


# ------------------------------- defects found by reading real output, week 5
#
# Four checks below were wrong when first shipped, and the full suite passed on
# all four. Every one was caught by reading an audit report on real records, not
# by a test. These tests exist so that cannot recur silently; each fails on the
# version of the check that shipped.

def flat(**kw):
    """A record carrying its configuration as top-level fields, with no nested
    `cell` dict. This is what the pipeline actually writes, and the difference
    matters: `cell_of` falls back to the nested dict, so a fixture that has one
    cannot reproduce a collapsed grouping."""
    r = rec(**{k: v for k, v in kw.items() if k not in ("mapping", "n_qubits")})
    r.pop("cell", None)
    for f in ("mapping", "n_qubits"):
        if f in kw:
            r[f] = kw[f]
    return r


def control_correlated_within_seed(mean, sd, n_seeds=20, n_settings=4):
    """A control where the settings sharing a seed share its split.

    The independent unit is the seed. Repeating each seed's value across four
    settings leaves the standard deviation unchanged and multiplies the record
    count by four, so a standard error taken over records is half what it should
    be and every sigma doubles.
    """
    z = np.arange(n_seeds, dtype=float)
    z = (z - z.mean()) / z.std(ddof=1)
    out = []
    for s, zi in enumerate(z):
        for k in range(n_settings):
            out.append(rec(seed=s, method=f"m{k}", roc=mean + sd * zi,
                           ap=0.5154, shuffled=True))
    return out


def test_negative_control_measures_spread_over_splits_not_records():
    """Shipped dividing by sqrt(80) on 20 seeds and reported +2.68 sigma.

    The fifth instance of the unit-of-analysis error in this project, and the
    second inside the tool written to catch it.
    """
    ctrl = control_correlated_within_seed(mean=0.5137, sd=0.0438)
    o = audit.check_negative_control(paired(n_seeds=4), ctx(control=ctrl))
    assert o.numbers["ROC-AUC"]["n_units"] == 20      # splits, not the 80 records
    assert abs(o.numbers["ROC-AUC"]["sigma"]) < 2.0
    assert o.status == audit.PASS
    assert "80 records" in o.detail                   # both numbers stay visible


def test_negative_control_still_fails_a_genuine_leak():
    """Halving the sigma must not disarm the check."""
    ctrl = control_correlated_within_seed(mean=0.60, sd=0.0438)
    o = audit.check_negative_control(paired(n_seeds=4), ctx(control=ctrl))
    assert o.status == audit.FAIL


def test_negative_control_says_so_when_it_cannot_identify_splits():
    ctrl = [{k: v for k, v in r.items() if k != "seed"}
            for r in control_correlated_within_seed(0.5010, 0.0438)]
    o = audit.check_negative_control(paired(n_seeds=4), ctx(control=ctrl))
    assert "ASSUMED" in o.detail


def test_cross_arm_refuses_a_grouping_that_does_not_identify_one_record():
    """Shipped keeping whichever record it read last and reporting a clean PASS.

    A one-configuration quantum file against a fifteen-configuration classical
    file intersects to no configuration fields at all; every configuration then
    collapses onto one key. The label fingerprint does not catch it, because
    configurations differ in the feature mapping and not in the labels.
    """
    # No nested `cell` dict, top-level configuration fields instead: the shape
    # this project's own pipeline emits, and the shape that collapses.
    one_cell = [flat(seed=s, method="quantum", mapping="pca", n_qubits=12)
                for s in range(20)]
    many = [flat(seed=s, method="rbf", mapping=m, n_qubits=q)
            for s in range(20) for m, q in (("pca", 8), ("pca", 12), ("kbest", 8))]
    o = audit.check_cross_arm(one_cell, ctx(compare=many, cell_fields=[],
                                            compare_fields=[]))
    assert o.status == audit.FAIL
    assert o.numbers["max_records_per_group"] == 3
    assert "--cell-fields" in o.detail


def test_cross_arm_still_pairs_a_well_specified_comparison():
    fields = ["mapping", "n_qubits"]
    q = [flat(seed=s, method="quantum", mapping=m, n_qubits=q_)
         for s in range(20) for m, q_ in (("pca", 8), ("pca", 12))]
    c = [flat(seed=s, method="rbf", mapping=m, n_qubits=q_, ap=0.66)
         for s in range(20) for m, q_ in (("pca", 8), ("pca", 12))]
    o = audit.check_cross_arm(q, ctx(compare=c, cell_fields=fields,
                                     compare_fields=fields))
    assert o.status == audit.PASS
    assert o.numbers["n_seeds"] == 20


def test_tuning_symmetry_excludes_methods_with_no_parameters_to_tune():
    """Shipped warning on every file containing a linear baseline.

    A linear kernel has no structural parameter, so it cannot be untuned. The
    check must distinguish an empty parameter set from a fixed one, or it fires
    on almost every comparison and carries no information.
    """
    linear = [rec(seed=s, method="linear", params={}, C=[0.1, 1.0][s % 2])
              for s in range(6)]
    q = tuned("quantum", [0.25, 0.5, 1.0, 2.0], "bandwidth")
    c = tuned("rbf", [1e-3, 1e-2, 1e-1, 1.0], "gamma")
    o = audit.check_tuning_symmetry(q, ctx(compare=linear + c))
    assert o.status == audit.PASS
    assert o.numbers["per_method"]["linear"]["has_parameters"] is False


def test_tuning_symmetry_names_the_parameters_that_were_held_fixed():
    """A reader has to be able to see it was `bandwidth` and not a label."""
    q = [rec(seed=s, method="quantum", params={"embedding": "iqp", "reps": 1},
             C=1.0) for s in range(6)]
    o = audit.check_tuning_symmetry(
        q, ctx(compare=tuned("rbf", [1e-3, 1e-2, 1e-1], "gamma")))
    assert o.status == audit.WARN
    assert "embedding, reps" in o.detail
    assert o.numbers["fixed"]["quantum"] == ["embedding", "reps"]


def test_surrogate_will_not_call_a_sample_straddling_the_floor_a_separation():
    """Shipped returning PASS at a median of 0.0012 against a floor of 0.0010.

    1.2x the resolution limit, on six samples, with no spread reported, while
    the full per-family analysis of the same arm concludes the kernel IS its
    surrogate. The measurement agreed with that analysis; the verdict rule did
    not.
    """
    hook = FakeHook()
    hook.gaps = [2e-4, 2e-4, 6e-4, 6e-4, 6e-4, 6e-4]
    o = audit.check_surrogate(paired(n_seeds=4), ctx(hook=hook))
    assert o.status == audit.WARN
    assert "too close to call" in o.detail
    assert o.numbers["n_below_floor"] == 2
    assert o.numbers["min_abs_d_normap"] < o.numbers["median_abs_d_normap"]


def test_surrogate_pass_requires_every_sampled_record_above_the_floor():
    o = audit.check_surrogate(paired(n_seeds=4), ctx(hook=FakeHook(surrogate_gap=0.20)))
    assert o.status == audit.PASS
    assert o.numbers["n_below_floor"] == 0
    assert "can separate from its surrogate and still lose to it" in o.detail


def test_unit_of_analysis_warns_on_a_single_configuration_file():
    """Shipped as a SKIP reading "independent units cannot be identified".

    They can: the split is the unit. An 80-record file that is 20 splits scored
    by four methods reads as 80 observations unless the report says otherwise,
    and the skip fired exactly there.
    """
    recs = [flat(seed=s, method=f"m{k}", mapping="pca", n_qubits=12)
            for s in range(20) for k in range(4)]
    o = audit.check_unit_of_analysis(recs, ctx(cell_fields=["mapping", "n_qubits"]))
    assert o.status == audit.WARN
    assert o.numbers["n_seeds"] == 20 and o.numbers["n_records"] == 80
    assert "n=20, not n=80" in o.detail


def test_unit_of_analysis_skips_when_records_really_are_the_units():
    recs = [flat(seed=s, method="only", mapping="pca", n_qubits=12)
            for s in range(20)]
    o = audit.check_unit_of_analysis(recs, ctx(cell_fields=["mapping", "n_qubits"]))
    assert o.status == audit.SKIP
    assert "the same thing here" in o.detail


def qbench_ordered(n_cells=15, n_seeds=20, settings=("a1", "a2", "i1", "i2")):
    """Records in the order the pipeline writes them: configuration, then seed,
    then setting. The block structure is what a stride aliases against."""
    out = []
    for c in range(n_cells):
        for s in range(n_seeds):
            for st in settings:
                out.append(flat(seed=s, method=f"quantum-{st}",
                                mapping="pca", n_qubits=4 + 2 * (c % 5)))
    return out


def test_hook_sample_spans_methods_instead_of_aliasing_with_file_order():
    """A stride returned six records that were all one method on two seeds.

    1200 records written in blocks of 80 (4 settings x 20 seeds) against a
    stride of 200: every pick lands on setting index 0. Every hook-based number
    in that report described one kernel family while the text called it a sample
    of the file.
    """
    recs = qbench_ordered()
    assert len(recs) == 1200
    stride = recs[::len(recs) // 6][:6]
    assert len({r["method"] for r in stride}) == 1          # the defect
    assert len({r["seed"] for r in stride}) == 2

    picked = audit._sample(recs, 6)
    assert len(picked) == 6
    assert len({r["method"] for r in picked}) == 4          # every setting
    assert len({r["seed"] for r in picked}) > 2


def test_hook_sample_is_deterministic_and_handles_small_files():
    recs = qbench_ordered(n_cells=1, n_seeds=2)
    assert audit._sample(recs, 6) == audit._sample(recs, 6)
    assert len(audit._sample(recs, 100)) <= len(recs)
    assert audit._sample(recs, 1)


def test_hook_checks_report_which_methods_they_sampled():
    """A sample that cannot be seen is a sample that quietly becomes one family
    again. Both hook checks name their coverage in the report text."""
    recs = qbench_ordered(n_cells=2, n_seeds=4)
    o = audit.check_conditioning(recs, ctx(hook=FakeHook(cond=1e15)))
    assert "method(s)" in o.detail and o.numbers["methods_sampled"]
    o2 = audit.check_surrogate(recs, ctx(hook=FakeHook(surrogate_gap=0.20)))
    assert "covering" in o2.detail and len(o2.numbers["methods_sampled"]) > 1


def with_inner(rho_sign):
    """Records whose inner score tracks, or anti-tracks, the test score."""
    out = []
    for i in range(20):
        ap = 0.70 + 0.002 * i
        r = rec(seed=i, ap=ap)
        r["inner_score"] = 0.6 + 0.002 * i * rho_sign
        out.append(r)
    return out


def test_selection_warns_when_the_inner_score_does_not_predict_the_endpoint():
    """The check computed this correlation, printed it, and passed regardless.

    It returned "Selection auditable" on a real arm whose correlation was
    -0.367: a measurement taken correctly and then not used, which is the same
    failure as the two verdict-rule defects found earlier in week 5.
    """
    o = audit.check_selection_leak(with_inner(-1), ctx())
    assert o.status == audit.WARN
    assert o.numbers["spearman_inner_vs_test"] < 0
    assert "ranking noise" in o.detail
    assert "does not invalidate the held-out estimates" in o.detail


def test_selection_passes_when_the_criterion_tracks_the_endpoint():
    o = audit.check_selection_leak(with_inner(+1), ctx())
    assert o.status == audit.PASS
    assert o.numbers["spearman_inner_vs_test"] > 0


def test_selection_skips_when_the_inner_score_is_constant():
    """This returned PASS, and nothing in the suite noticed.

    `with_inner(0)` gives every record the same inner score, which is what an
    arm looks like when tuning had nothing to choose between. scipy then returns
    NaN with a ConstantInputWarning, and `nan <= 0` is False, so the WARN branch
    never fired and the audit reported "selection is auditable and the criterion
    tracks the endpoint" about a correlation that does not exist.

    The helper this check now uses supported the constant case from the start
    and no test ever passed 0. The check was converted to SKIP -- the audit's
    own rule is that a check which cannot answer its question says so and names
    why, exactly as `test_selection_skips_without_inner_scores` requires for a
    missing field. Absence is never read as a pass.
    """
    o = audit.check_selection_leak(with_inner(0), ctx())
    assert o.status == audit.SKIP
    assert o.status != audit.PASS, "the defect: an undefined rho read as a pass"
    assert "constant" in o.detail
    assert "spearman_inner_vs_test" not in (o.numbers or {}), (
        "a number that does not exist must not be reported as one")


def test_selection_skips_when_the_endpoint_is_constant():
    """The other input. Every record scoring identically on the test set is
    equally undefined, and equally not a pass."""
    recs = []
    for i in range(20):
        r = rec(seed=i, ap=0.70)          # identical test score
        r["inner_score"] = 0.6 + 0.002 * i
        recs.append(r)
    o = audit.check_selection_leak(recs, ctx())
    assert o.status == audit.SKIP
    assert "constant" in o.detail


def test_selection_skip_names_the_record_count():
    """A refusal that does not say how much data it had is not actionable."""
    o = audit.check_selection_leak(with_inner(0), ctx())
    assert o.numbers["n_records"] == 20


def test_checks_skip_on_absent_required_fields_instead_of_raising(tmp_path):
    """The first foreign audit reported `check raised KeyError('n_test')` as a
    FAIL, three times, on a deposit whose endpoint was balanced accuracy rather
    than average precision. Unanswerable is not failed, and a stranger reading
    that output would conclude the tool was broken."""
    recs = [{"method": m, "seed": 42, "n_train": 60, "final_converged": True,
             "test_balanced_accuracy": 0.47}
            for m in ("hardware", "ideal-sim", "noisy-sim")]
    p = tmp_path / "foreign.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in recs))
    _, outs = audit.run(str(p), None, audit.DEFAULT_PRECISION_FLOOR)

    raised = [o for o in outs if "raised" in o.detail]
    assert not raised, f"checks still crashing: {[o.name for o in raised]}"
    by_name = {o.name: o for o in outs}
    for name in ("chance correction", "statistical power", "precision floor"):
        assert by_name[name].status == audit.SKIP
        assert "n_test" in by_name[name].detail
    # the one thing this file CAN answer still answers
    assert by_name["solver health"].status == audit.PASS


def test_a_genuinely_broken_check_still_fails_loudly():
    """The skip guard must not become a blanket exception swallow."""
    def exploding(recs, ctx):
        raise RuntimeError("boom")
    saved = audit.CHECKS
    try:
        audit.CHECKS = [exploding]
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.jsonl")
            open(p, "w").write(json.dumps(rec()) + "\n")
            _, outs = audit.run(p, None, audit.DEFAULT_PRECISION_FLOOR)
        assert outs[0].status == audit.FAIL and "boom" in outs[0].detail
    finally:
        audit.CHECKS = saved


def test_schema_failure_does_not_invalidate_checks_that_still_answered():
    """A blanket "nothing below can be trusted" is false whenever a check that
    does not need the absent fields still produced a reading. On the first
    foreign audit that line sat above the only measurement in the report."""
    recs = [{k: v for k, v in rec().items()
             if k not in ("n_test", "test_base_rate", "test_average_precision",
                          "test_roc_auc")} for _ in range(3)]
    o = audit.check_schema(recs, ctx())
    assert o.status == audit.FAIL
    assert "nothing below can be trusted" not in o.detail.lower()
    assert "still answer" in o.detail and "Discount" in o.detail
    assert len(o.detail) < 260, "a foreign reader should not get an essay here"
