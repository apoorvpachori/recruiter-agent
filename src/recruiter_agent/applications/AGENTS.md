# Application workflow guidance

- Follow [`CONTRIBUTING.md`](../../../CONTRIBUTING.md) and the [application architecture](../../../docs/architecture/applications.md).
- Keep the workflow separate from model tools. Never expose browser controls, form values, selected file bytes, or submit authority to the model.
- Restrict navigation and browser destinations to public HTTPS Ashby hosts. Preserve the outbound write block until explicit confirmation.
- Never send user answers or files during preparation/review. Send them only on the one-use confirmed submit path; never retry an uncertain submission.
- Keep draft state and files in memory only. Do not log, persist, trace, or add real profile/resume data to tests or docs.
- Require visible review of supported fields, a current one-use review token, and a separate literal user confirmation. Update `applied` only after a recognized Ashby success response.
- Add synthetic focused tests for success, stale review, unsupported/unknown controls, and uncertain submit outcomes.
