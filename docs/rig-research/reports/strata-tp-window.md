# Strata tp window

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

First post-guard window. Host-transport arm passed the short and long-read cases; shared-prefix concurrent reuse was unconfirmed. The 44 GiB no-lending arm ran out of time. No later arm was run. A router regression passed after a test-only link correction.

## Retained tables

### Per arm

| Arm | Settings | S1 | S2 (128k read beside a 2,048-token writer) | S3 (two 128k at once) |
|---|---|---|---|---|
| Router guard test | n/a | n/a | n/a | n/a, **pass** (rc 0) |
| 1 | `FNX_PEER=0 FNX_PF_PEER=0`, RAM 36, reserve 640, 2 slots, ctx 131072 | pass | pass | "reuse unconfirmed" (no crash) |
| 2 | peer off, RAM 44 (no lending) | pass | incomplete: cancelled at 90,112 / 127,958 tokens, 357 s | not run |
