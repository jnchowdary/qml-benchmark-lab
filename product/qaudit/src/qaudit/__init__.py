"""qaudit: reports what a benchmark results file can and cannot establish.

Extracted from the QML Benchmark Lab research repository. The checks and
their wording are unchanged from that repository's scripts/audit.py; what
this package adds is that it installs and runs without the research
environment, which pulled in qiskit, pennylane, scikit-learn and pandas to
read a JSONL file.
"""

__version__ = "0.1.0"
