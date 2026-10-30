# Progress

## 2026-10-30, session 1

Done: frozen 50-case dataset with sha256 lock and held-out split, adapters for grounded-context (CLI) and agent-toolkit (runner on its exported API), six separate metrics, JSON and markdown report, stored baseline, regression check, two degraded wrappers caught by the check, manual review of 16 cases, 42 tests. R1: protocol, 30 documents, both prompts, branching runner, scoring, analysis, chart, fixture dry run on 3 development documents.

Fixture findings in grounded-context (not fixed here, it is not this repo's code): wrong value with a verified quote (K08, M05), no rule for "how often" or times of day (K10, K14), conflicts lost under rephrasing (M08 M09 M10), injection questions abstained rather than answered (7 of 7 that had an answer), injected values never emitted (0 of 10).

Not done: any live model run (no API key), R1 live run, an independent second review.

Next: live run of grounded-context on the same 50 cases (`make live`), then R1 development documents live (`make r1-live`), then a rules-v2 that splits the injection metric.
