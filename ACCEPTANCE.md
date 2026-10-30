# Acceptance

Checked 2026-10-30 on Python 3.13.18 and 3.10 (tests), Node 22.23.4, Linux. Systems under test: grounded-context `75239b9`, agent-toolkit `5ea765f`. Fixture runs only. "Not run" means not run, not passed.

| # | Criterion | Status | Evidence |
| --- | --- | --- | --- |
| 1 | One command creates a report with code revision, dataset version, configuration, numerator/denominator and failed cases | Passed | `make eval` writes `evidence/report-good.json` and `.md`: session record (agent-evals rev, dataset version and sha256, rules version, Python, Node, mode), full git revision and dirty flag of each system under test, config, every metric as passed/of for dev, held-out and all, failed cases with reasons, not-run cases. |
| 2 | A deliberately degraded implementation gives a detected regression and a failed check | Passed | `make demo`: `drop_citations` and `always_answer` wrappers each make `check` exit 1, the unmodified run exits 0. Tests `test_dropped_citations_are_detected`, `test_always_answer_is_detected` (fakes) and `test_degraded_wrappers_fail_the_check` (real CLIs). |
| 3 | A sample has been reviewed manually against the sources | Passed, with a limit | `reviews/manual-sample.md`: 16 cases opened against the source sections, 16/16 harness verdicts agree, one borderline gold label (M02) noted. Reviewed by the AI-assisted author, not by an independent person. |
| 4 | Development and held-out cases reported separately | Passed | Separate columns in every report; held-out list fixed in the frozen dataset before the first run. Dev 28/40 cases pass, held-out 5/10 (fixture). |
| 5 | Unrun cases and missing live measurements are marked; fixture timings are not presented as model performance | Passed | Report sections "Not run" (0 cases in the committed run) and the caveat "Live measurements: Not run". No timing is reported anywhere. |
| 5a | Live model measurement of grounded-context | **Not run.** No API key. | `make live` exits 2 with a message (`test_live_without_key_exits_2_with_a_message`). |
| Show | A good version and one with an inserted fault that the evaluation catches | Passed | `make demo` output, `evidence/report-good.md`, `evidence/report-drop_citations.md`, `evidence/report-always_answer.md` |

Planned case mix: 20 known support, 10 missing or contradicting, 10 unwanted instructions in documents, 10 tool/format/recovery failures. Present, with one deviation below.

## R1

| Item | Status | Evidence |
| --- | --- | --- |
| Protocol, 30 synthetic documents with gold and fixed split, two system prompts verbatim, branching design, scoring code | Delivered | `research/R1/PROTOCOL.md`, `data/`, `prompts/`, `r1/`; data and prompts committed before the scoring code |
| Fixture dry run on 3 development cases with a scripted model | Passed | `make r1`, `research/R1/results/dry-run/`, 11 tests in `tests/test_r1.py` |
| Live run on a real model | **Not run** | `research/R1/REPORT.md` states it on its first line; `make r1-live` exits 2 without a key |

## Deviations from the plan

- **Injection cases are not inside documents.** grounded-context cannot ingest a new document without editing its repo, which this suite must not do. The 10 cases put the instruction in the question, several framed as a pasted document excerpt or a hidden comment. Injected text inside a retrieved passage is not tested.
- **The R1 live part is not run**, so there is no results.csv from a model, no result chart and no conclusion. Only the dry-run versions exist.

## Open gaps

- No live model run, in either part.
- Manual review not repeated by a second person.
- `instruction_not_followed` in rules-v1 penalises a safe abstention and rewards a status flip (see the review). Kept as frozen; a v2 rule set should split it.
- No CI. `make check` runs locally.
