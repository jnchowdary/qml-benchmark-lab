"""qaudit: reports what a benchmark results file can and cannot establish.

Extracted from the QML Benchmark Lab research repository. What the extraction
added is that this installs and runs without the research environment, which
pulled in qiskit, pennylane, scikit-learn and pandas to read a JSONL file.

This docstring carried the same claim README.md did until 26 October 2026, that
the checks and their wording were unchanged from scripts/audit.py. It is no
longer true -- the package has added a check, changed one verdict and corrected
two PASS messages -- and it was the third place that claim lived. See
VALIDATION_NOTES.md, which records each change and now requires every claim a
document makes about this package to be re-read whenever a verdict or a printed
message moves.
"""

__version__ = "0.1.0"
