# Agent evaluations

The eval suite is a local regression check for assistant behavior. It runs synthetic cases against the production agent graph and tools, using scripted model turns, fixture-only web/search responses, and a fresh temporary SQLite database per case.

## Run the suite

From the repository root, run:

```sh
uv run python -m recruiter_agent.evals
```

The command has no options. By default it needs no provider credentials or network access. It prints each case's checks, tool calls and results, and final response; it always writes the same information to `.eval-results/latest.md` (overwriting the previous run). A nonzero exit means one or more checks failed. LangSmith tracing is disabled.

To add LLM-judge scores to the same run, set `EVAL_JUDGE_ENABLED=true` in `.env`. The judge uses the configured Fireworks model and scores relevance, evidence grounding, and uncertainty calibration from 0 to 2. Every dimension must score at least 1 for the judge check to pass. Judge calls send only synthetic case requests, expectations, observed tool traces, and scripted responses to Fireworks. They can incur provider costs; leave the setting disabled for a fully offline run.

## Cases and assertions

Cases are newline-delimited JSON in `evals/cases/core.jsonl`; their schema is in `src/recruiter_agent/evals/models.py`. Each case declares a synthetic user request, optional local fixtures, scripted assistant turns, and at least one hard expectation. Assertions can check required tool calls, forbidden tool calls, unchanged or expected database state, and short required/forbidden response fragments.

Keep cases synthetic. Never use real profile values, resumes, application notes, private URLs, or production traces. Prefer assertions about actions, persisted state, and safety behavior over exact prose. Scripted turns validate tool wiring and graders; they do not measure whether a live model independently selects the expected tool.

Reports contain synthetic case responses, tool arguments/results, and (when enabled) judge rationales. They are written locally under the Git-ignored `.eval-results/` directory with owner-only permissions; inspect them before sharing.
