# Architecture: AI job-search copilot

**Status:** Initial proposal
**Principle:** Keep business rules deterministic and auditable; use an LLM only for bounded extraction, comparison, and draft language. For the first slice, prefer a draft-and-review workflow over uncontrolled browser automation.

## 1. Recommended MVP stack

- Python 3.12+
- FastAPI + Pydantic for an HTTP API and typed request/response contracts
- LangGraph for bounded orchestration of job analysis and application preparation (keep the first workflow synchronous unless pause/resume proves necessary)
- Versioned local JSON files for the MVP profile and application tracker; no database, ORM, or migration framework initially
- LangChain model adapters only where convenient; keep model calls behind a small application-owned interface
- `httpx` + HTML parsing for publicly accessible job pages, with strict URL/network restrictions
- Pytest, Ruff, mypy (or pyright), and structured JSON logging with sensitive-field redaction
- Optional later: Playwright for user-visible, user-controlled form filling. Do not make it a dependency of the initial draft-only milestone.

Pin dependencies and model/provider configuration. Avoid coupling product logic to a specific LLM provider or browser automation library.

## 2. High-level components

```text
Candidate UI / API client
        |
FastAPI routes + auth (single-user local mode initially)
        |
Application services / policy checks
        |------------------------|
LangGraph workflow           File repository
  - URL validation             - owner profile/preferences
  - fetch/extract               - jobs/applications/events
  - fit analysis
  - draft answers
  - approval interrupt
        |                         |
External job page (read-only)  Versioned JSON files
        |
LLM adapter (bounded calls; structured schemas; no tools by default)
```

### Responsibility boundaries

- **API:** Validate inputs, authenticate/authorize, expose typed responses, return graph state/checkpoint IDs; no prompt logic.
- **Services:** Enforce product policy (consent, profile provenance, sensitive-question rules, approval gate, dedupe), coordinate repositories and graph.
- **Graph nodes:** Perform small, typed tasks and return state updates. Nodes do not mutate arbitrary state or bypass service policy.
- **Adapters:** Job page fetcher, parser, LLM, browser interaction, clock. All external effects behind interfaces for testability.
- **Persistence:** Use validated, versioned JSON files for the one user's profile, preferences, jobs, and application events. Keep status events append-only; write atomically and back up safely. Avoid storing raw page or resume content unless necessary.

## 3. LangGraph design

### Graph A: analyze and prepare (MVP)

```text
START
  -> validate_job_url
  -> load_candidate_profile
  -> fetch_job_page
  -> extract_job (structured output, provenance)
  -> analyze_fit (rules first; optional LLM summary)
  -> extract_application_questions (if available)
  -> map_verified_profile_facts
  -> draft_non_sensitive_answers (only where supported)
  -> flag_missing_or_sensitive_answers
  -> human_review interrupt
  -> persist_draft_and_event
  -> END
```

- Use a typed `TypedDict`/Pydantic state containing `user_id`, `job_url`, `job_id`, `profile_version`, extracted job facts, evidence, fit criteria, question/answer drafts, review decisions, `thread_id`, and errors.
- Keep graph state minimal; references/IDs are preferable to full resume text and sensitive values.
- Avoid persistent graph checkpoints in the first MVP where possible: run the analysis synchronously and save only the reviewed application draft and resulting status/events. If a workflow interrupt requires a checkpoint, keep it in a separate local file with an explicit retention policy; do not add a database just for orchestration. Add durable shared checkpoint storage only when the product needs it.
- Interrupt at review and resume using the same thread/checkpoint after an explicit user action. A graph interrupt is not itself proof of user authorization; re-check policy and authenticated user at the API/service boundary before resuming.
- Make nodes idempotent. Use stable job/application IDs and idempotency keys so a retry cannot create duplicate records or submit twice.
- Capture node errors as typed outcomes. Do not silently fall back to fabricated answers when extraction/model calls fail.

### Graph B: submission (later, gated)

Only introduce after draft-and-review is stable. Require a review snapshot/hash, authenticated user, explicit per-application confirmation, and an unexpired approval record. Then:

```text
approval_check -> open_supported_form -> compare_current_fields_to_reviewed_snapshot
  -> fill_approved_fields -> stop_for_captcha_or_unexpected_state
  -> final_confirmation_interrupt -> submit_once -> verify_receipt
  -> record_submitted | record_submission_unknown
```

Never retry a submit after timeout or ambiguous browser state without first verifying whether the application was accepted. Do not bypass CAPTCHA, anti-bot controls, MFA, or site restrictions. A user-visible browser handoff is the safe fallback.

## 4. Data model (initial)

- `profile.json`: versioned owner profile, verified facts, and preferences. Its schema is MVP-specific; no user/tenant abstraction yet. Optional sensitive fields should be omitted unless the owner explicitly chooses to store them.
- `applications.json`: versioned array of jobs/applications, review drafts, and append-only status events; deduplicate by canonical job URL.
- Optional later `runs/`: expiring graph checkpoints only if pause/resume is needed.

Normalize statuses using enums and validate transitions in service code. Validate JSON on load, write via temp-file + atomic replace, and create a backup before destructive edits. File permissions should restrict access to the owner. Do not commit real profile data, application answers, or run files; use a redacted example schema/fixture in git. Keep the file paths configurable and ignored by git.

## 5. API sketch

- `GET /healthz`
- `GET|PUT /v1/profile` — the single local user's profile; validate and version updates.
- `POST /v1/jobs/analyze` — `{job_url}`; starts or resumes analysis and returns run ID/state.
- `GET /v1/runs/{run_id}` — progress, result summary, pending-review requirement.
- `POST /v1/runs/{run_id}/review` — approved edits / missing field decisions; resume preparation.
- `POST /v1/applications/{id}/status` — validated manual status update, creates event.
- `GET /v1/applications` and `GET /v1/applications/{id}` — list/detail.
- `DELETE /v1/profile` and export endpoint — privacy controls for local files.
- Later only: `POST /v1/applications/{id}/submit/confirm` with explicit confirmation and reviewed snapshot token.

Use request IDs, idempotency keys on create/resume actions, bounded payloads, and clear errors (`unsupported_url`, `page_unavailable`, `needs_user_input`, `review_required`, `submission_unknown`).

## 6. Security and privacy controls

- Keep the MVP single-user and local-only; bind any API to loopback and do not expose it to a network. Add authentication and multi-user ownership checks before any non-local deployment.
- SSRF defense: allow only HTTPS Ashby-owned domains and explicit approved redirects; resolve and reject private, loopback, link-local, and reserved IPs; limit redirects, response size, timeouts, MIME types, and decompression; revalidate each redirect and DNS result.
- Never accept arbitrary browser URLs for server-side fetches. Do not execute JavaScript from fetched pages in the server.
- Separate secrets from source control; use `.env.example` with placeholders only; add `.env`, real profile/application JSON, checkpoints, resumes, and browser profiles to `.gitignore`. Commit only a schema or synthetic fixture.
- Redact profile values, application answers, session cookies, auth headers, and raw prompts from logs/traces. Retain only safe IDs/statuses and diagnostics.
- Apply request/body limits, CORS allowlist, rate limits, CSRF controls where relevant, and secure cookies if browser sessions are introduced.
- Local files inherit the host filesystem's protection; document that limitation and recommend full-disk encryption. Avoid storing demographic answers in the MVP. For a deployed product, add encryption at rest and consider per-field encryption/key rotation before storing sensitive values.
- Provide profile delete/export and workflow state retention/cleanup. Do not train on candidate data by default.
- Treat fetched web content as untrusted prompt-injection input. Use it only as quoted source material for structured extraction; no tools or arbitrary actions are granted to the extractor.

## 7. Testing strategy

- Unit: URL normalization and allowlist, HTML extraction, profile fact provenance, fit tri-state logic, sensitive/missing answer rules, status transition matrix, dedupe, approval expiry/snapshot matching.
- Graph: deterministic node tests with fake fetcher/LLM/checkpointer; interrupt/resume and idempotency tests.
- API: schema, auth/ownership, safe error responses, profile CRUD and run lifecycle.
- Integration: fixture-based Ashby pages (including changed markup, incomplete content, malicious page instructions); JSON schema validation, atomic-write, backup, and corruption-recovery tests.
- E2E: draft creation and review with a fake ATS, not real submissions. Submission tests must use a sandbox/test form and verify no second submit on ambiguous result.
- Evaluation: curated job/profile examples with expected extracted fields and fit rationale; review answer grounding and hallucination rates.

## 8. Suggested repository layout

```text
.
├── README.md
├── pyproject.toml
├── .env.example
├── data/                    # gitignored real profile and application files
│   ├── profile.json
│   └── applications.json
├── docs/
│   ├── product-spec.md
│   └── architecture.md
├── src/recruiter_agent/
│   ├── api/                 # FastAPI routers and dependencies
│   ├── domain/              # schemas, enums, policy and transitions
│   ├── services/            # use cases, review/approval policy
│   ├── graph/               # LangGraph state, nodes, builder
│   ├── adapters/            # Ashby fetcher/parser, LLM, JSON file persistence
│   └── main.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
└── scripts/
```

## 9. Implementation sequence

1. Confirm local-only deployment, the owner's profile fields, retention, and that MVP excludes automatic submission (recommended).
2. Add Python project metadata, lint/type/test configuration, secret-safe `.gitignore`, and a minimal FastAPI health endpoint.
3. Define Pydantic schemas and versioned JSON file persistence; test profile CRUD, provenance, optional sensitive fields, atomic writes, and application events.
4. Implement secure Ashby URL validation + fixture-based read-only fetch/extraction. Do not support arbitrary URLs.
5. Implement deterministic fit scoring/statuses (`match`, `mismatch`, `unknown`) and evidence presentation.
6. Add LangGraph analysis/draft flow with fake adapters; introduce checkpointing and interrupt/resume only if the UX needs it.
7. Add API endpoints and a simple UI/CLI for profile, analysis, review, and tracking.
8. Run evaluation on representative sample roles; address extraction errors and grounded answer quality before any submission work.
9. Only then assess legal/terms, accessibility, and technical constraints for a user-mediated submission experiment.

## 10. First vertical slice

The smallest useful end-to-end build is: configure the owner's local profile -> submit one supported Ashby URL -> extract job facts from a saved fixture/live public page -> compare preferences with explicit evidence -> save the role and `researching` status to a validated local JSON file -> return a human-readable fit report. This validates the file format, fetching boundary, product value, and test setup without prematurely automating risky form submission or adding a database.
