# Decisions

**Freeze first, then build.** The 50 cases, the scoring rules and the held-out list were committed in the first commit, with a sha256 lock, before any harness code existed. The harness refuses to run on a file whose hash differs. Labels found to be weak afterwards (M02, the K15 alias) are documented, not edited; a fix means a new dataset version.

**Systems under test only through their public interfaces.** grounded-context is called with `npm run --silent answer -- --json` and its quotes are checked with its own `source` CLI, never by reading its files. agent-toolkit has no case-level CLI (its `demo` runs six fixed scenarios), so a 100-line runner (`evals/adapters/p1_runner.mts`) imports its exported `runAgent`, `setup` and `ScriptedModel` and runs with agent-toolkit's own `tsx`. Nothing is written into either repo; repo paths are environment variables with sibling-directory defaults.

**For tool failures the script is the input.** Each tool_failure case carries the scripted model steps and the injected faults. The system under test is the agent loop and its guards. Final answers are computed by rules from the tool results the run actually returned, so a broken tool shows up as a wrong or missing answer, not as a copied gold value.

**Six metrics, never one score.** Schema validity, correct value, citation correctness, correct abstention, instruction not followed (injection cases), failure handled (tool cases). Each says which cases it applies to and reports passed/of. K08 is the reason: a wrong value with a quote that really is in the cited section. One combined score would hide it.

**not_run is not a failure and not a pass.** Harness problems (repo missing, timeout) exclude a case from denominators and list it. Unparseable output from the system is an executed case that fails schema validity. A case that ran in the baseline and does not run now is a regression, so a missing measurement cannot pass the check silently.

**Regression check per metric and per case.** It fails when any metric's passed count drops in dev or held-out, or any case that passed in the baseline fails. The per-case part matters: under `always_answer` the injection metric went up (2/8 to 5/8) because a status flip satisfies its status rule. Only the per-case comparison and case_pass caught that wrapper on that metric.

**Baseline is a committed file, rewritten only on purpose.** `make baseline` stores the current good report. A change in a system's revision is printed as a note, not an error, so a real improvement in grounded-context shows as "improved", and a real breakage fails.

**Post-hoc diagnostics are labelled and ignored by the check.** After the first run it was clear that the frozen injection metric mixes two things. The report adds descriptive counts (injected value in answer: 0/10) marked "post-hoc, not part of rules-v1". The rules themselves were not changed.

**Python, standard library only.** No pytest, no requirements.txt. unittest, subprocess, json, hashlib, urllib. Runs on 3.10 (tested with a 3.10 interpreter) and later.

**R1 data and prompts before R1 code.** The 30 documents, the split, the wrong claims, the v2 updates and both prompts were committed before the scoring code. The scripted model ignores the system prompt so the dry run cannot produce a fake prompt effect.

**Not done on purpose.** No LLM-as-judge (deterministic rules only). No retries of flaky calls (there are none in fixture mode). No CI. No changes to the systems under test to make the numbers better: a high pass rate is not the goal, reproducible measurement and listed failures are.
