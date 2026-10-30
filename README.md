# agent-evals

A 50-case evaluation suite for two earlier projects in this portfolio: [grounded-context](https://github.com/farrebutterfly-rgb/grounded-context) (document answers with citations) and [agent-toolkit](https://github.com/farrebutterfly-rgb/agent-toolkit) (a tool-calling agent loop). Gold answers, allowed sources and scoring rules were frozen with a sha256 before the first run. Every run writes a versioned report with the revision of each system under test, and a regression check fails when a deliberately broken implementation is swapped in.

It also holds a small research case, [R1 "Evidence under pressure"](research/R1/PROTOCOL.md), designed and dry-run but not yet run on a model.

## Quick start

Python 3.10 or later (standard library only), Node 22 or later. The two systems under test are checked out next to this repo:

```
some-folder/
  agent-evals/
  grounded-context/     or set GROUNDED_CONTEXT_REPO=/path/to/it
  agent-toolkit/        or set AGENT_TOOLKIT_REPO=/path/to/it
```

```bash
make install     # checks versions, repos and the dataset lock; runs npm ci in a repo without node_modules
make eval        # ONE command: 50 cases -> evidence/report-good.{json,md}, then the regression check
make demo        # good run passes the check, two degraded wrappers fail it; then the R1 dry run
make test        # 42 tests
make check       # test + eval + demo
```

| Variable | Default | Meaning |
| --- | --- | --- |
| `GROUNDED_CONTEXT_REPO` | `../grounded-context` | grounded-context checkout |
| `AGENT_TOOLKIT_REPO` | `../agent-toolkit` | agent-toolkit checkout |
| `EVAL_WORKERS` | `4` | parallel CLI calls |
| `EVAL_CALL_TIMEOUT_S` | `60` | per call; a timeout marks the case not_run |
| `PYTHON` (make) | `python3` | interpreter |

Live run (costs money, needs a key, never run so far): `make live` runs grounded-context with `--live`; `make r1-live` runs R1. Both exit 2 with a message when `ANTHROPIC_API_KEY` is missing.

## What the demo shows

Excerpt of `make demo` (fixture, grounded-context `75239b9`, agent-toolkit `5ea765f`):

```
== 1. the unmodified systems, checked against the stored baseline
                                     dev       held-out
  case_pass                    28/40 (70%)     5/10 (50%)
  schema_valid                40/40 (100%)   10/10 (100%)
  correct_value                18/26 (69%)      4/7 (57%)
  citation_correct             20/30 (67%)      4/8 (50%)
  correct_abstention           29/40 (72%)     5/10 (50%)
  instruction_not_followed       2/8 (25%)       0/2 (0%)
  failure_handled               8/8 (100%)     2/2 (100%)
  not run: 0   failed: K01, K08, K10, K14, M02, M05, M08, M09, M10, I01, I02, I03, I04, I07, I08, I09, I10
  check: no regression against baseline

== 2. degraded wrapper `drop_citations`: returns the answer but drops every citation / evidence id
  citation_correct              0/30 (0%)       0/8 (0%)
  REGRESSION T10 passed in baseline, fails now: citation_correct: no evidence_ids
  check: FAILED, regression against baseline

== 3. degraded wrapper `always_answer`: turns every abstention or conflict into status answered
  REGRESSION dev correct_abstention: 27/40 now, 29/40 in baseline
  REGRESSION I05 passed in baseline, fails now: correct_abstention: status answered, acceptable ['insufficient_evidence']; ...
  check: FAILED, regression against baseline

== summary
  good            check exit 0  (as expected)
  drop_citations  check exit 1  (as expected)
  always_answer   check exit 1  (as expected)
```

How to read it. The 17 failures are real failures of grounded-context's deterministic extractive answerer on questions phrased differently from its own labelled set, not harness errors (16 were checked by hand, see [reviews/manual-sample.md](reviews/manual-sample.md)). The most instructive one is K08: asked for the priority 2 response time it answers "2 hours" (the priority 1 value) and cites a quote that really is in the section, so citation checking passes and only the value check catches it. Injection questions were never obeyed (the injected value appears in 0 of 10 answers) but 7 of them were abstained on instead of answered, which the frozen injection metric counts as a failure. agent-toolkit contained every injected tool, format and recovery failure (10/10).

## How it works

```
data/cases-v1.json  --sha256 must match data/cases-v1.lock.json-->  evals.dataset.load()
        |
        |  grounded-context cases (40)                 agent-toolkit cases (10)
        v                                              v
 GroundedContextAdapter                         AgentToolkitAdapter
   npm run --silent answer -- --json "<q>"        agent-toolkit/node_modules/.bin/tsx p1_runner.mts
   npm run --silent source -- <doc> <sec>           imports runAgent, setup, ScriptedModel
        |                                              scripted steps + faults from the case
        |          optional DegradedAdapter wrapper (drop_citations | always_answer)
        v                                              v
 raw system output, untouched  ------------------------+
        |
        v
 scoring.score_case()   rules-v1, each metric applies to its own cases
   schema_valid | correct_value | citation_correct (quote is an exact substring of the section
   as printed by the source CLI; evidence id was really fetched) | correct_abstention |
   instruction_not_followed | failure_handled
        |
        v
 runner -> evidence/report-<variant>.json + .md + observations-<variant>.jsonl
           dev and held-out apart, numerator/denominator, failed and not-run cases, revisions
        |
        v
 regression.compare(report, baseline/baseline.json)
   any metric count down, any baseline-passing case failing, any baseline case not run -> exit 1
   other dataset or rules version -> exit 2
```

| File | Role |
| --- | --- |
| `data/cases-v1.json`, `.lock.json` | 50 frozen cases, scoring rules, held-out list, sha256. See [data/README.md](data/README.md). |
| `evals/adapters/grounded_context.py` | Shells out to grounded-context's `answer` and `source` CLIs. |
| `evals/adapters/agent_toolkit.py`, `p1_runner.mts` | Runs agent-toolkit's agent loop on scripted failure cases through its own tsx. |
| `evals/adapters/degraded.py` | The two deliberately broken wrappers. |
| `evals/scoring.py` | rules-v1, one function per metric, aggregation with not_run kept apart. |
| `evals/runner.py`, `evals/report.py` | Runs everything, writes JSON, markdown and raw observations. |
| `evals/regression.py` | Baseline comparison and exit codes. |
| `baseline/baseline.json` | Stored good run the check compares against. |
| `reviews/manual-sample.md` | 16 cases checked by hand against the sources. |
| `research/R1/` | Protocol, 30 documents, two prompts, branching runner, scoring, dry run, [REPORT.md](research/R1/REPORT.md). |
| `tests/` | 42 tests: scoring, dataset lock, regression on fakes, real CLIs, R1. |

## Reusable interface

```bash
python3 -m evals run --variant good|drop_citations|always_answer [--live] [--k N]
python3 -m evals check --variant good      # exit 0 ok, 1 regression, 2 not comparable
```

`evidence/report-<variant>.json` has `session`, `systems`, `config`, `results.{dev,heldout,all}.<metric> = {passed, of}`, `by_category`, `failed_cases[{id, split, category, status, failures}]`, `not_run_cases`, `cases`, `diagnostics`, `caveats`. A new system plugs in as an adapter with `run(cases) -> {case_id: RawResult}` and `describe()`.

## What this proves and what it does not

- It proves the measurement: frozen labels, separate metrics with stated denominators, quotes checked against the system's own source text, held-out reported apart, and a regression gate that two plausible bugs cannot get through.
- Every number is from fixture mode: grounded-context's deterministic extractive answerer and a scripted model in agent-toolkit. It says nothing about any language model. Live measurements are Not run.
- 50 cases written by one author who had read both systems. The held-out split was fixed before the first run, but it is not unseen by the author.
- Injected instructions are only tested in the question text; grounded-context has no ingestion path for new documents.
- Synthetic gold labels are not professional legal, tax or accounting validation.
- R1 is a protocol and a dry run. It has no result.

Design trade-offs are in [DECISIONS.md](DECISIONS.md). Status per criterion is in [ACCEPTANCE.md](ACCEPTANCE.md).

Built with AI assistance (Claude); every change is reviewed and run locally.
