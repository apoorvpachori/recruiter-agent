# Ashby application workflow

## Scope and ownership

The application workflow is separate from the model-driven agent. The React screen lets the user start with a public Ashby job URL, review supported form fields, edit answers, and attach a resume. `src/recruiter_agent/applications/` owns the field mapping, short-lived draft, browser session, review snapshot, and one-time submission transition. The API only validates requests and maps domain errors. The model receives no browser session, form values, file bytes, or submit tool.

Only HTTPS URLs on `jobs.ashbyhq.com` can start a draft. Browser requests are limited to public HTTPS destinations under Ashby-owned `ashbyhq.com` and `ashbycdn.com`; DNS results must be public. External signed file-upload hosts are deliberately blocked, so a form that relies on one may need manual completion. Unsupported controls, ambiguous Apply actions, CAPTCHA, changed form structure, and invalid native constraints also stop the automated flow for manual handling.

## State and flow

```mermaid
sequenceDiagram
  actor User
  participant UI as Application UI
  participant API as FastAPI
  participant Service as Application service
  participant Browser as Restricted Ashby session
  participant DB as Local jobs DB
  User->>UI: Enter Ashby job URL
  UI->>API: POST /v1/applications/prepare
  API->>Service: Validate URL and load local profile
  Service->>Browser: Open public form with outbound writes blocked
  Browser-->>Service: Supported visible fields
  Service->>DB: Create/update job as draft_ready
  Service-->>UI: Short-lived draft and review token
  User->>UI: Edit answers / select resume
  UI->>API: Save reviewed snapshot
  User->>UI: Confirm explicit submission
  UI->>API: POST /{draft_id}/confirm
  API->>Service: Check confirmation, token, required fields, live form
  Service->>Browser: Send form data once
  Browser-->>Service: Recognized success or uncertain outcome
  Service->>DB: Mark applied only after recognized success
  Service-->>UI: Terminal outcome; clear answer values
```

Draft answers and selected file bytes exist only in process memory and the isolated browser context, with a 20-minute expiry. They are not persisted to SQLite, included in agent traces, or logged. Shutdown closes active browser contexts. A newly saved answer rotates the one-use review token; submission requires the current token, a literal `user_confirmed: true`, all required answers, and a live form snapshot that still matches review.

The browser request policy blocks non-read requests during initial page loading. Once fields are discovered, it blocks all further page requests and WebSockets while values are being prefetched or reviewed. On confirmation it permits traffic only to public Ashby hosts, uploads any selected file, clicks exactly one recognized submit control, and never retries. If a success message is not recognized or the submit call errors, the result is `uncertain`; the UI tells the user to verify on Ashby before trying again. The job tracker changes to `applied` only after Ashby shows a recognized success message.

## Data and trust boundaries

- Profile prefilling maps only exact contact labels (name, email, phone, LinkedIn). It does not draft free-text answers.
- The UI displays every supported visible control and its source. Unknown controls stop preparation; page text is untrusted and never treated as instructions.
- The local API receives field answers and optional PDF/DOC/DOCX bytes. File content is held in memory and is not attached to the browser form until confirmation.
- Once confirmed, answers and any selected file are sent to Ashby. This is an external consequential action, so the confirmation screen must identify the destination and require a separate user action.
- The application endpoint is unauthenticated like the rest of the local API. Keep it bound to loopback; do not expose it to a LAN or public network.
- The browser adapter requires the Playwright Chromium binary, installed with `uv run playwright install chromium`.

## Implementation and verification

- Backend contract/service/adapter: [`src/recruiter_agent/applications/`](../../src/recruiter_agent/applications/)
- HTTP endpoints: [`src/recruiter_agent/api/applications.py`](../../src/recruiter_agent/api/applications.py)
- User review UI: [`frontend/src/components/AshbyApplication.tsx`](../../frontend/src/components/AshbyApplication.tsx)
- Safety and state tests: [`tests/test_applications.py`](../../tests/test_applications.py)
- Durable rationale: [ADR 0001](decisions/0001-ashby-reviewed-application-workflow.md)

Keep the supported host and form controls narrow. Never expose selectors, browser commands, or submission authority to the model. Any retry, broader ATS support, persistent drafts/files, or unattended application behavior requires a new review of these boundaries and documentation.
