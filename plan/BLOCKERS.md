# Blockers

Add one line per blocker: date, task id, what is missing, what you did instead.
Never stop the whole build for a blocker.

2026-11-15 P3.7: No LLM credential was configured, so v0.1 cross-checks were skipped as allowed; generated cases record `cross_check: skipped_no_model` and the review queue is empty.

2026-11-16 P5.5: LLM_API_KEY and LLM_BASE_URL are not configured, so the live reviewer baseline could not run; saved the documented deterministic scanner-backed stub baseline for the dev split (54 cases).

2026-11-16 P7.1: MERGEGUARD_GITHUB_TOKEN and TEST_REPO are not configured, so live GitHub verification was skipped; implemented and tested the client against recorded HTTP fixtures, and added a credential-gated read-only live test.
