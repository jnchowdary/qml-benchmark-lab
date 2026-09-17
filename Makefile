export PYTHONPATH := src

.PHONY: install test quick clean

install:
	python -m pip install -r requirements.txt

test:
	python -m pytest tests/ -q --cov=qbench --cov-report=term-missing

quick:
	python scripts/run_quick_benchmark.py --config configs/quick.yaml --max-seconds 1800

clean:
	rm -rf results/kernels/* results/runs/* .pytest_cache .coverage
