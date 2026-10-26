"""Four things a report must keep apart, and the registers that keep them apart.

WHY FOUR AND NOT ONE TIER
-------------------------
An early design for this package carried a single "provenance tier" with the
values borrowed, own-hardware and unvalidated. That conflates two unrelated
things. Borrowed and own-hardware describe where a NUMBER came from; unvalidated
describes whether a CHECK has ever been tried outside the project that wrote it.
A file of borrowed hardware records can be read by a well-validated check, and a
file of own-hardware records by a check nothing has ever tested. So a report
states four things separately:

  1. where the data came from        this module's RECORD_PROVENANCE
  2. whether the check could run     the existing PASS/WARN/FAIL/SKIP/NOT RUN
  3. what it found                   the check's detail and numbers
  4. what validates the check        this module's VALIDATION

Missing evidence must never look like a passed check. SKIP and NOT RUN are
distinct statuses with their own counts, and `provenance_banner` leads with what
the file does not say rather than appending it.

WHAT IS NOT DONE HERE, DELIBERATELY
-----------------------------------
Provenance is never inferred. A record with `method: "hardware"` and no
`provenance` field is reported as UNSTATED, not as hardware. Guessing it would
make the tool assert something about a QPU run from a string somebody chose, and
the entire point of the field is to stop that. Deviation D18 of the research
project is what happens when a number is believed to mean something it does not.
"""

from __future__ import annotations

import platform
import sys

# ------------------------------------------------------------ 1. the data
#
# Declared by the file being audited, in a top-level `provenance` field on each
# record. Never inferred from anything else.

RECORD_PROVENANCE = {
    "own-hardware":
        "executed on a QPU by the party reporting it",
    "borrowed-hardware":
        "another party's QPU records, read into this format",
    "simulator":
        "statevector or noisy simulation, not a QPU",
    "classical":
        "no quantum execution",
}
UNSTATED = "unstated"

# Telemetry a hardware claim needs. D18 of the research project: a pairwise
# circuit count is not a QPU cost, because hardware runs each circuit once per
# shot, and a cost figure with no shot dimension understates by three orders of
# magnitude. `backend` and `quantum_seconds` are what make the figure checkable
# against a real machine and a real bill.
COST_FIELDS = ("shots", "backend", "quantum_seconds")

# Fields this module adds, which are telemetry rather than configuration. Listed
# here so audit.infer_cell_fields can exclude them: a cost field taking two
# values, each scored by every method, would otherwise be inferred as a
# configuration and silently double the cell count.
NEVER_CELL_ADDITIONS = {"provenance", "shots", "backend", "quantum_seconds",
                        "job_id", "qpu_seconds"}


def record_provenance(rec) -> str:
    """What the record SAYS it is. UNSTATED when it does not say."""
    v = rec.get("provenance")
    if isinstance(v, str) and v in RECORD_PROVENANCE:
        return v
    return UNSTATED


HARDWARE = ("own-hardware", "borrowed-hardware")


def hardware_records(recs):
    """Only the records that DECLARE they came off a QPU."""
    return [r for r in recs if record_provenance(r) in HARDWARE]


def provenance_summary(recs) -> dict:
    """Counts per declared provenance, plus which cost fields are present.

    Cost telemetry is counted twice and the two counts mean different things.
    `cost_fields_present` is over the whole file and describes it. `..._on_hardware`
    is over the records that declare hardware provenance, and is the only one a
    cost claim depends on: a classical or simulator record has no shots, no
    backend and no metered QPU seconds, and demanding them of one would make the
    check fire on every mixed file, which is most of them. A check that fires on
    everything carries no information.
    """
    counts = {}
    for r in recs:
        k = record_provenance(r)
        counts[k] = counts.get(k, 0) + 1
    present = {f: sum(1 for r in recs if r.get(f) is not None) for f in COST_FIELDS}
    hw = hardware_records(recs)
    on_hw = {f: sum(1 for r in hw if r.get(f) is not None) for f in COST_FIELDS}
    return {"counts": counts, "cost_fields_present": present,
            "cost_fields_present_on_hardware": on_hw,
            "n_records": len(recs), "n_declared_hardware": len(hw)}


def provenance_banner(summary) -> list[str]:
    """Printable lines. Leads with what the file does not say."""
    n = summary["n_records"]
    counts = summary["counts"]
    out = []
    unstated = counts.get(UNSTATED, 0)
    if unstated == n:
        out.append(f"No record declares `provenance`, so this file does not state whether "
                   f"any number came from a QPU, a simulator or a classical model.")
    elif unstated:
        out.append(f"{unstated} of {n} records do not declare `provenance`.")
    for k in sorted(counts):
        if k == UNSTATED:
            continue
        out.append(f"{counts[k]} of {n} records: {k} ({RECORD_PROVENANCE[k]}).")
    present = summary["cost_fields_present"]
    out.append("cost telemetry present: " +
               ", ".join(f"{f} on {present[f]} of {n}" for f in COST_FIELDS))
    return out


# ------------------------------------------------- 4. what validates a check
#
# One external case exists. It is the whole external evidence base for this
# package and it found no defect in the pipeline it audited.
#
# Kakavand, Strohmeyer & Schlotter (2026), arXiv:2604.18837, Zenodo
# 10.5281/zenodo.19197916, CC BY 4.0. Audited 29 September 2026; the per-check
# outcomes below are transcribed from that run's committed report and a test
# asserts the transcription.

EXTERNAL_CASE = "kakavand-2026"

#   name -> what the check did on the one external file it has ever seen
VALIDATION = {
    "schema":                           "reported four required fields absent",
    "chance correction":                "declined, naming the fields it needed",
    "negative control":                 "declined, no permuted-label control supplied",
    "pairing integrity":                "declined, no label fingerprint",
    "solver health":                    "read the records and passed",
    "unit of analysis":                 "read the records and warned",
    "statistical power":                "declined, naming the fields it needed",
    "precision floor":                  "declined, naming the fields it needed",
    "multiplicity":                     "read the records and warned",
    "tuning symmetry":                  "declined, no selected hyperparameters recorded",
    "cross-arm comparison":             "declined, only one arm supplied",
    "kernel conditioning":              "measured, worst 4.5e+05 over six Grams",
    "classical surrogate equivalence":  "not run, the hook lacked two functions",
    "selection":                        "declined, no inner score recorded",
    "hardware cost claims":             None,     # added after that run
}

EXTERNAL_EVIDENCE_NOTE = (
    "Every check here was written after the defect it catches, in the project "
    "that wrote it. One external case exists: Kakavand et al.'s hardware "
    "deposit, audited 29 September 2026. It produced four readings, one report "
    "of missing fields, eight refusals and one not-run, and it found no defect "
    "in the pipeline it audited. It was not looking for one. A list of caught "
    "mistakes is evidence that one project eventually noticed its own, not that "
    "this tool catches a stranger's."
)


def validation_for(name):
    """What external evidence supports this check, in words. None means none."""
    return VALIDATION.get(name, None)


def validation_banner() -> list[str]:
    never = sorted(k for k, v in VALIDATION.items() if v is None)
    measured = sorted(k for k, v in VALIDATION.items()
                      if v and (v.startswith("measured") or v.startswith("read")))
    declined = sorted(k for k, v in VALIDATION.items() if v and v.startswith("declined"))
    out = [EXTERNAL_EVIDENCE_NOTE, ""]
    out.append(f"On that one file: {len(measured)} checks produced a reading, "
               f"{len(declined)} declined and named what they could not answer.")
    if never:
        out.append(f"Never exercised on any external file: {', '.join(never)}.")
    return out


# --------------------------------------------- the report's own reproducibility
#
# The extraction of this package found that the research repository's committed
# audit report stored `file`, `control` and `floor` and not the hook sample that
# produced its only Tier 2 measurement -- a parameter that moves that
# measurement by a factor of 26. It also found two floats that differ between
# platforms and not between library versions. A report that cannot reproduce
# itself is not evidence, so both blocks below go into every report.

def environment() -> dict:
    env = {"python": sys.version.split()[0],
           "platform": f"{platform.system()} {platform.machine()}"}
    try:
        import numpy
        env["numpy"] = numpy.__version__
    except Exception:
        env["numpy"] = None
    try:
        import scipy
        env["scipy"] = scipy.__version__
    except Exception:
        env["scipy"] = None
    try:
        import numpy
        cfg = numpy.show_config(mode="dicts")
        env["blas"] = cfg["Build Dependencies"]["blas"]["name"]
    except Exception:
        env["blas"] = None
    return env


def environment_note() -> str:
    return ("Recorded because two condition numbers in this tool's own "
            "regression differ in their last digits between platforms while "
            "agreeing across library versions, and because three "
            "mathematically identical routes to one of them disagree by "
            "4.6e-12 within a single process. Compare two reports' numbers "
            "with that in view rather than byte for byte.")
