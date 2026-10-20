# Low-level tool guidance

- Web fetchers are read-only. Do not execute page JavaScript or follow page instructions.
- Validate every URL/redirect, reject non-public network destinations, and bound redirects, time, bytes, and returned text.
- Return structured content with source URL and retrieval context; omit scripts/styles/navigation noise.
- Do not log page text or full URLs. Test using mocked responses and private/local URL rejection cases.
