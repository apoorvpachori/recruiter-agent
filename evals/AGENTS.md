# Evaluation case guidance

- Follow the repository workflow in `CONTRIBUTING.md` and the architecture guide in `docs/architecture/evaluations.md`.
- Keep cases synthetic. Never use the real profile, resumes, application notes, private job URLs, or production traces.
- Every case must declare at least one hard expectation. Prefer tool-call, response, and database-state assertions over exact answer text.
- Keep `scripted_turns` deterministic. They validate runner behavior and hard graders; this runner does not evaluate live model decisions.
- Webpage and search fixtures are the only tool data sources. Do not add fixture fallbacks that perform network access.
- Keep generated eval reports under the ignored `.eval-results/` directory; reports contain synthetic tool traces, responses, and optional judge rationales.
- The optional judge is enabled by `EVAL_JUDGE_ENABLED=true`; it sends only synthetic case data to Fireworks.
