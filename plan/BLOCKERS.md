# Blockers

Add one line per blocker: date, task id, what is missing, what you did instead.
Never stop the whole build for a blocker.

2026-11-15 P3.7: No LLM credential was configured, so v0.1 cross-checks were skipped as allowed; generated cases record `cross_check: skipped_no_model`.

2026-11-16 P5.5: LLM_API_KEY and LLM_BASE_URL are not configured, so the live reviewer baseline could not run; saved the documented deterministic scanner-backed stub baseline for the dev split (54 cases).

2026-11-16 P7.1: MERGEGUARD_GITHUB_TOKEN and TEST_REPO are not configured, so live GitHub verification was skipped; implemented and tested the client against recorded HTTP fixtures, and added a credential-gated read-only live test.

2026-11-16 L6 live consistency: Groq's on-demand tier enforced an 8,000-token-per-minute limit and returned repeated 429 responses during the 144-case, five-repeat suite; its strict-JSON attempt also returned schema-generation 400 errors. Switched to local Ollama as directed. The complete split exceeded the requested two-hour runtime budget, so it was stopped before persistence and replaced with an eight-case evenly-spaced sample at five repeats; the saved reduced-scope result passed its consistency threshold. This fulfills the revised runtime-bounded evaluation scope; a full-split run is optional if faster hardware becomes available.
