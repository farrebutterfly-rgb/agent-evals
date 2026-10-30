.PHONY: install test eval demo check baseline live r1 r1-live
PYTHON ?= python3
install:   ## check Python 3.10+, Node 22+, the two sibling repos and the dataset lock; npm ci there if node_modules is missing
	$(PYTHON) -m evals doctor
test:      ## unit tests, regression tests on fakes, integration tests against the real CLIs (skipped if a repo is missing)
	$(PYTHON) -m unittest discover -s tests -t .
eval:      ## ONE command: run all 50 cases, write evidence/report-good.{json,md}, check against baseline/baseline.json
	$(PYTHON) -m evals eval
demo:      ## good run passes the check, each degraded wrapper fails it; then the R1 fixture dry run
	$(PYTHON) -m evals demo
	cd research/R1 && $(PYTHON) -m r1 dry-run
check: test eval demo
baseline:  ## rewrite the stored baseline from evidence/report-good.json (deliberate act, commit the diff)
	$(PYTHON) -m evals baseline
live:      ## grounded-context with --live; needs ANTHROPIC_API_KEY, costs money; never run so far
	$(PYTHON) -m evals run --live
r1:        ## R1 fixture dry run, 3 development cases, scripted model, no cost
	cd research/R1 && $(PYTHON) -m r1 dry-run
r1-live:   ## R1 real model run; needs ANTHROPIC_API_KEY, costs money; Not run
	cd research/R1 && $(PYTHON) -m r1 live
