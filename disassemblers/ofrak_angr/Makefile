PYTHON=python3

.PHONY: install
install:
	$(PYTHON) -m pip install .

.PHONY: develop
develop:
	# PIP_CONSTRAINT pins setuptools<82 so that pkg_resources is available during the angr build on
	# aarch64. pip>=82 uses an isolated build environment that drops pkg_resources. This constraint
	# can be removed once the base Docker image is bumped to Python 3.10+.
	PIP_CONSTRAINT=constraints.txt $(PYTHON) -m pip install -e . --config-settings editable_mode=compat

.PHONY: inspect
inspect:
	$(PYTHON) -m mypy

.PHONY: test
test: inspect
	$(PYTHON) -m pytest -n auto --cov=ofrak_angr tests
	fun-coverage --cov-fail-under=100
