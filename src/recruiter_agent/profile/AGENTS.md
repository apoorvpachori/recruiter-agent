# Profile data guidance

- `data/profile.json` is the local source of truth and is Git-ignored.
- Keep the schema typed, versioned, and strict enough to catch typos.
- Empty/null preferences mean unknown or unset; never infer sensitive data or preferences.
- Do not include private profile values in prompts, logs, fixtures, or committed examples.
- Add schema tests with synthetic data only.
