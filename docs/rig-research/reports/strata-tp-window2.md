# Strata tp window2

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

Peer transport passed S1/S2, including a long read alongside a writer. S3 failed a harness cache-reuse assertion, not an engine error. Both S3 requests read cold; the intended cached-prefix trigger was not established. No peer-off fallback was eligible.

## Retained tables

### Second TP diagnostic window

| Arm | Result | Measured speed / coverage |
|---|---|---|
| A: `FNX_PEER=1 FNX_PF_PEER=1` | **PASS**, S1 and S2 | S1: both 64 tokens, API decode 16.3 and 66.9 tok/s. S2: 2,048-token writer at 13.8 tok/s beside a cold 127,955-token read in 99.188s (1,290 tok/s), then 512 tokens at 19.7 tok/s. |
| B: same peer-on, S3 | **FAIL: test condition**, no engine error | Second send 20.029s later; both prompts 128,569 tokens and both `cache_n=0`. Both completed 64 tokens. API prefill 114.0s / 208.3s; decode 0.3 / 17.8 tok/s. Requested shared-prefix rewind/lane-change case **unconfirmed**. |
| C: peer-off fallback | **NOT RUN** | A passed, so this branch was not eligible. |
