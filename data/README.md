# Data provenance

Everything here is synthetic. The cases were written by hand for this repo on 2026-10-30. Dataset version: `agent-evals-cases-v1`.

The cases point at data owned by the two systems under test. Nothing from those repos is copied here except the ids and short values needed as gold labels:

- grounded-context, dataset `bizdocs-v1`: ten invented business documents in `grounded-context/data/docs`. Company names, addresses and amounts are invented.
- agent-toolkit, dataset `suppliers-v1`: twelve invented suppliers in `agent-toolkit/data`. Every email uses the reserved `.example` domain (RFC 2606).

## Files

| File | What it is |
| --- | --- |
| `cases-v1.json` | 50 labelled cases, the scoring rules (`rules-v1`) and the held-out split. |
| `cases-v1.lock.json` | sha256 of `cases-v1.json`, recorded when the file was frozen. The harness refuses to run when the hash differs. |

The lock was committed in its own commit before any harness code existed (see `git log -- data/`), so the gold labels could not be adjusted to the results.

## Cases

| Category | Count | System | What a correct system does |
| --- | --- | --- | --- |
| `known_support` | 20 | grounded-context | Answers with the right value and a citation whose quote is really in the cited section. |
| `missing_or_conflict` | 10 | grounded-context | 6 have no support: `insufficient_evidence`. 4 ask about the two facts where a policy and a memo disagree: `conflict` with both sides cited. |
| `prompt_injection` | 10 | grounded-context | The question carries an unwanted instruction, written as plain text or as a pasted "document excerpt". The system answers the real question from the corpus (or abstains when the corpus has no answer) and does not obey. |
| `tool_failure` | 10 | agent-toolkit | A scripted model makes a bad tool call, hits a timeout, a 503 or a 404, submits an ungrounded or malformed final answer, loops, or replies with text only. The agent loop must contain the failure and end with the expected status. |

Each case has `expected_status`, `acceptable_statuses`, `expected_answer` (a list of accepted aliases, or null), `forbidden_in_answer`, and `allowed_sources` (`doc_id#section_id` for grounded-context, supplier ids for agent-toolkit). Tool-failure cases also carry the scripted model steps, injected faults, `expected_error_codes` and `expected_final_rejections`.

## Known limitation of the injection cases

grounded-context has no ingestion path: its corpus is the fixed folder `data/docs`, and its CLI takes only a question. Writing new documents into that repo would modify the system under test, which this suite must not do. So the injected instructions travel in the question, sometimes framed as a quoted document excerpt or hidden comment. This tests that injected text reaching the answerer is not obeyed. It does not test injected text inside a retrieved passage. That needs an ingestion interface in grounded-context and is listed as an open gap in ACCEPTANCE.md.

## Held-out split

10 cases (`K04 K09 K14 K18 M05 M09 I04 I09 T05 T08`) were chosen before the first run, stratified by category. Nothing in this repo is tuned on any case, but the same author wrote the cases and has read the systems under test, so "held-out" means "not looked at while building the harness", not "unseen by the author".

Synthetic gold labels are not professional legal, tax or accounting validation.
