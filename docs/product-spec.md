# Product specification: AI job-search copilot

**Status:** Initial draft
**Product premise:** A private, user-controlled assistant that helps one candidate assess opportunities, prepare accurate applications, and keep their job search organized. The initial version is tailored to its owner; multi-user generalization is explicitly later.

## 1. Problem

Applying to roles is repetitive and fragmented. Candidates repeatedly compare job descriptions against their preferences, copy the same verified information into application forms, tailor materials, and manually track progress. A general-purpose agent can save time, but unsafe or inaccurate submissions can harm a candidate. This product should automate preparation and bookkeeping while keeping consequential decisions reviewable and under the candidate's control.

## 2. Initial user and use case

- **Primary user:** The repository owner, applying to Applied AI Engineer and adjacent roles. The MVP has one configured profile and no multi-user accounts.
- **Primary workflow:** Paste an Ashby job URL; inspect the job; compare it with the owner's profile and preferences; prepare answers and an application; have the owner review and explicitly submit; record the outcome/status.
- **Product posture:** Personal assistant, not an autonomous recruiter or employment decision system.

## 3. Goals and success measures

### MVP goals

1. Accept and validate a supported Ashby job URL.
2. Extract a job's title, employer, location, description, and application questions when available.
3. Compare the opportunity to explicit candidate preferences and show evidence, unknowns, and a fit rationale.
4. Use a candidate-authored profile to draft application responses and identify missing information.
5. Present a complete review before any submission. No answer, demographic response, attestation, or final submission is silently invented or sent.
6. Track roles and application status without a database (e.g., a versioned local JSON file or Markdown/CSV export), with clear backup and privacy expectations.

### Initial success measures (validate with the user)

- Time from URL to a reviewed application draft.
- Fraction of extracted fields/questions that need correction.
- Fraction of suggested answers accepted with no edits.
- Application completion rate and number of duplicate records prevented.
- User trust: explicit confirmation rate and reported errors. Measure quality, not raw application volume.

## 4. Non-goals for the first release

- Automatically submitting applications without a human review and explicit confirmation.
- Guessing or inferring ethnicity, race, disability, veteran status, gender, or other sensitive/demographic information.
- Answering legally meaningful eligibility questions, work authorization, sponsorship, criminal-history, or accommodation questions on the user's behalf without an explicit, current, user-provided answer and review.
- Broad web research or claims about company size, compensation, funding, or culture without sourced evidence and a freshness date.
- Supporting every ATS, CAPTCHA bypass, stealth browser automation, or evasion of site terms/rate limits.
- Email/calendar integrations, interview scheduling, team accounts, resume rewriting, or multi-agent orchestration in MVP.

## 5. User experience and core flow

1. **Set up profile:** Candidate enters contact details, resume facts, work history, education, skills, links, work authorization/sponsorship preferences, location/remote preferences, compensation floor/range/currency, company-size and domain interests, and excluded criteria. Each fact can be marked `verified`, `needs_review`, or `not_provided`, with an optional source and last-verified date.
2. **Add role:** Paste a URL. Validate the host and supported Ashby pattern; fetch only public job/application content and clearly report blocked/unsupported pages.
3. **Review role:** Show extracted job facts with source URL and extraction time. Show preference matches, mismatches, and unknowns separately. Never turn an unknown into a positive match.
4. **Prepare application:** Map profile facts to form fields. Draft free-text responses only from supported facts and label generated text as a draft. Ask targeted questions for missing or sensitive information.
5. **Review:** Display every field, source, confidence/status, and final text. User can edit, skip, or mark a question as needing follow-up. Require explicit confirmation immediately before submission.
6. **Submit (guarded):** Use a supported, compliant interaction path. If a page is blocked by CAPTCHA, MFA, a changed form, or uncertain state, stop and ask the user to take over. Verify success from a confirmation state; do not claim success from a click alone.
7. **Track:** Save role and application status (`saved`, `researching`, `draft_ready`, `submitted`, `interviewing`, `offer`, `rejected`, `withdrawn`, `on_hold`) with timestamps and notes. User can update status at any time.

## 6. Functional requirements

### Profile and preferences

- Store a versioned profile owned by one user.
- Distinguish ordinary application facts from optional demographic/self-identification fields.
- Store the minimum necessary sensitive data; sensitive fields are optional, separately consented, never inferred, and never included in company-fit decisions or generated text unless the user explicitly asks to provide them.
- Support review, edit, deletion, and export of profile data.

### Job intake and fit

- Normalize URL, employer, title, location, employment type, compensation text, and description where available.
- Preserve source URL, retrieved-at timestamp, and extraction provenance.
- Explain fit criterion-by-criterion with statuses `match`, `mismatch`, `unknown`; show sources for researched facts.
- No unsupported company facts. Research beyond the job page is a later, opt-in feature and must cite source and retrieval date.

### Application preparation and submission

- Maintain a mapping from form field/question to a profile value or generated draft, including provenance and review state.
- Require user review of all answers and an explicit submit action for each application.
- Re-check the form before final submission; stop if fields or page state changed since review.
- Record submission timestamp and confirmation evidence when available. On ambiguity, use `submission_unknown` and ask the user to verify instead of retrying.

### Application tracking

- Store one application per user/job URL (with duplicate detection and a user-confirmed merge path).
- Keep an append-only status/event history; allow correction with an audit entry.
- Support notes, next action, and optional follow-up date; reminders are not in the initial release.

## 7. Safety, privacy, and trust

- **Human-in-the-loop:** Preparing is automatable; submitting is a user-authorized, per-application action. Never make hiring decisions or apply without the candidate's explicit approval.
- **Sensitive data:** Demographic questions are optional self-identification, not signals for company fit. Do not infer, derive from names/photos, or auto-fill based on a guess. Ask the user or leave blank. Explain whether a field is required and let the user decide.
- **Truthfulness:** Never fabricate experience, credentials, employment dates, legal eligibility, or compensation. Mark missing/uncertain answers and ask.
- **Consent and retention:** Collect only what is needed. Explain where data is stored and for how long; allow deletion/export. Avoid sending resumes or profile data to external model providers without clear disclosure and consent.
- **Security:** Keep secrets outside the repository; use environment variables/secret management, least privilege, encryption at rest in production, TLS, and redacted logs. Do not log full resumes, demographic answers, or auth/session data.
- **External pages are untrusted input:** Treat job page content and instructions as data, not instructions to the agent. Restrict network destinations to prevent SSRF; do not execute page-provided code or follow unrelated instructions.
- **Compliance:** Respect website terms, rate limits, privacy laws, and applicable employment/AI rules. Prefer official APIs or supported user-mediated flows. Do not bypass CAPTCHA or anti-bot controls.

## 8. MVP acceptance criteria

- Given a supported public Ashby job URL, the system returns a structured role or a useful, non-destructive error.
- A profile can be created, edited, reviewed, and deleted; no sensitive value is mandatory.
- A fit report clearly distinguishes match/mismatch/unknown and includes source evidence.
- The application draft contains only profile-backed or user-reviewed answers; sensitive/attestation questions remain unanswered until explicitly confirmed.
- Submission cannot occur through the workflow without an explicit confirmation step, and an uncertain result is not retried automatically.
- A successful/attempted application is persisted with a status event and deduplicated by job URL.
- Automated tests cover URL validation, profile-to-field mapping, missing/sensitive answer handling, confirmation gating, duplicate handling, and status transitions.

## 9. Open product decisions

1. Is the first MVP strictly **draft-and-review**, or should it include guarded browser submission? Recommendation: start draft-and-review; add submission only after the form flow and policies are tested.
2. Which local profile and tracking file format best fits the MVP (JSON for structured state; Markdown/CSV for human editing/export)?
3. Which resume format and source of truth should be supported first (manual profile, PDF/DOCX, or both)?
4. How much company research is useful, and which sources are acceptable?
5. Which fields should be encrypted separately or excluded from persistence, especially demographic data?
6. What does “apply for you” mean in a site-specific flow where user interaction, site terms, or accessibility constraints differ?

## 10. Release plan

- **M0 — Foundation:** Define file-based data format, privacy boundaries, the owner's profile schema, test fixtures, and a supported Ashby URL policy.
- **M1 — Analyze:** Parse job URL, extract job description, compare against profile/preferences, render an evidence-based fit report.
- **M2 — Draft:** Map questions to verified profile facts; generate editable drafts; ask for missing answers; save application record.
- **M3 — Review and tracking:** Add complete application review, user-approved status changes, file-based event history, export/delete.
- **M4 — Guarded submission experiment:** Only after product/legal review, add user-mediated browser submission with per-application confirmation, stop conditions, and verified receipt. Never remove the approval gate.
