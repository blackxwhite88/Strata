# Strata tp window3

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

Sequential shared-prefix reuse passed. Cold decode was 58.0 tok/s and warm decode 87.5, with 127,934 reused tokens and FAST probes at both ends. This passed the predeclared research continuation rule; it did not establish a TP advantage over R2.

## Retained tables

### Third TP diagnostic window

| TP request | Decode | Generated-in ms | Drafts accepted / offered | Rounds | ms / round | cache_n |
|---|---:|---:|---:|---:|---:|---:|
| Cold | 58.0 tok/s | 8827 | 253 / 533 | 259 | 34.08 | 0 |
| Warm | 87.5 tok/s | 5851 | 471 / 488 | 41 | 142.70 | 127934 |
