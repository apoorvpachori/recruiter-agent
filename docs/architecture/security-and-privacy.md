# Security and privacy

## Trust boundaries

```mermaid
flowchart LR
  LOCAL[Local user and machine] -->|loopback HTTP| APP[Frontend and unauthenticated API]
  APP -->|configured request| MODEL[Fireworks]
  APP -->|configured request| SEARCH[Brave]
  APP -->|optional trace data| TRACE[LangSmith]
  WEB[Public web pages] -->|untrusted content| AGENT[Agent context]
  APP -->|local file access| PROFILE[Ignored profile JSON]
  APP -->|local file access| DB[(Ignored SQLite database)]
```

The frontend and API are local single-user components, not an authenticated multi-user service. Local network accessibility does not constitute authorization. Keep the backend bound to `127.0.0.1` in documented run commands. Any network exposure requires an authentication, authorization, and threat-model design first.

## Data leaving the machine

- Agent input and tool context are sent to the configured Fireworks model for inference.
- Search queries and URLs are sent to Brave when web search is used.
- Page requests go to the target public site when a page is fetched.
- If LangSmith tracing is enabled, trace data can include prompts, tool inputs, fetched content, and model responses.

Keep tracing disabled by default. If adding a provider or expanding a payload, document exactly what data it receives and whether the user can disable it. Never place credentials in browser-visible frontend configuration.

## Logging rules

Logs may contain safe operational metadata such as event name, request ID, method, route path, status, duration, provider name, and record ID. They must not contain request bodies, prompts, model responses, user notes, profile/resume contents, credentials, or full URLs. If a URL must be represented, use its hostname only. Preserve these rules in exception handling and new observability integrations.

## Web content and prompt injection

Fetched pages and search output are untrusted input. They may contain malicious instructions or misleading claims. The agent must use them only as evidence to assess, cite sources, preserve uncertainty, and never let them override system policy or user intent. Fetchers must enforce URL/public-destination checks, response bounds, and redirect safety; never add form interaction or page-script execution as a convenience feature.

## Database and actions

Model access is read-only and scoped to the jobs table. SQL mutations must remain impossible through that interface. Job creation and updates use the shared validated services and only occur on explicit user request. Application submission is outside current capability; any future external consequential action requires visible review and separate confirmation.

## Safe development

- Never read, print, stage, or commit `.env`, `data/profile.json`, resumes, or local SQLite files.
- Use synthetic profile and job data in fixtures and screenshots.
- Keep failures useful but content-safe; do not include full upstream response bodies or user input in errors/logs.
- Treat retrieved content, tool output, and model output as data, not trusted control instructions.
- Eval cases must use synthetic profile, job, and web data. Detailed reports can contain prompts, tool arguments/results, and model output; keep them local.
- Default eval runs use scripted responses and local fixtures only; they make no model or web calls and disable LangSmith export. Setting `EVAL_JUDGE_ENABLED=true` sends synthetic requests, expectations, traces, and responses to Fireworks for scoring.

Implementation entry points: [`settings.py`](../../src/recruiter_agent/settings.py), [`logging_config.py`](../../src/recruiter_agent/logging_config.py), [`main.py`](../../src/recruiter_agent/main.py), [`tools/read_webpage.py`](../../src/recruiter_agent/tools/read_webpage.py), and [`agent/tools.py`](../../src/recruiter_agent/agent/tools.py).
