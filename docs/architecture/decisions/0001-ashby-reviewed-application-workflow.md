# 0001. User-reviewed Ashby application workflow

- Status: accepted
- Date: 2026-10-26

## Context

The product should help the user apply to jobs, while the existing agent must remain unable to take consequential external actions without user control. Ashby's [application submission API](https://developers.ashbyhq.com/reference/applicationformsubmit) is an employer integration that requires candidate-write permissions; the [custom careers page API](https://developers.ashbyhq.com/docs/creating-a-custom-careers-page) is not a candidate-side credential path.

## Decision

Support the candidate-facing Ashby hosted application page through a dedicated user-facing workflow, separate from the model toolset. Limit initial support to public HTTPS `jobs.ashbyhq.com` pages and supported native controls. Keep draft answers and selected files in short-lived memory. Require visible review, a one-use review token, and separate explicit confirmation. Block page traffic during review and permit submission traffic only to Ashby hosts after confirmation. Permit one submit attempt; update the local job status only after a recognizable success response. Treat ambiguous outcomes as uncertain and never retry automatically.

## Consequences

The initial integration supports only Ashby-hosted application forms and may require manual completion for CAPTCHA, unsupported controls, or dynamic forms. Users explicitly authorize transmission of reviewed values and files to Ashby. The browser request policy blocks form writes until confirmation, and the agent cannot access the application service. See [applications](../applications.md) and [security and privacy](../security-and-privacy.md).
