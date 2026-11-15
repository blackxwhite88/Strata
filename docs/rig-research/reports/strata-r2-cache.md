# Strata r2 cache

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

X1 raised cache bytes to 32 GiB but left four entries: it still lost a prefix while using only 10.9 GiB. X2 enabled R3 concurrent prefill: writer gaps stayed under two seconds, but the third 128k read ended with non-finite logits and invalidated the whole cache. Reject R3 for this build/workload. X1 and X2 host states were unmatched.

## Retained tables

### Host memcpy probes (GB/s; FAST is 9 or more)

| Probe | Samples | State |
|---|---|---|
| X1 before | 9.68, 9.05, 9.41 | FAST |
| X1 after | 3.78, 3.80, 3.79 | SLOW |
| X2 before | 3.61, 3.57, 3.62 | SLOW |
| X2 after | not taken (guard ended the window) | n/a |

### X1: R2 + 32 GiB cache

| Phase | Aggregate tok/s | cache_n (lane 0 / 1) | TTFT s | Decode tok/s | Largest SSE gap s |
|---|---|---|---|---|---|
| Prime (cold) | n/a | 0 / 0 | 69.9 / 73.5 | 56.9 / 58.3 | 0.1 / 0.0 |
| Round 1 | 45.3 | 127,934 / 127,936 | 7.3 / 3.8 | 33.5 / 27.2 | 0.4 / 3.5 |
| Round 2 | 43.2 | 127,934 / 127,936 | 7.2 / 2.6 | 31.0 / 24.4 | 1.5 / 4.1 |
| Round 3 | 46.6 | 127,934 / 127,936 | 2.3 / 6.3 | 26.1 / 32.7 | 4.9 / 1.9 |
| Third-read writers (2048 tok) | n/a | 127,934 / 127,936 | 5.5 / 2.0 | 16.5 / 37.5 | **73.2** / 3.8 |
| Sustained 1 | 9.9 | 127,934 / **0** | 3.1 / **87.1** | 5.1 / 32.2 | **83.8** / 0.6 |
| Sustained 2 | 37.5 | 127,934 / 127,936 | 4.4 / 9.6 | 22.5 / 28.9 | 4.9 / 1.5 |
| Sustained 3 | 38.7 | 127,934 / 127,936 | 8.7 / 2.7 | 28.7 / 21.6 | 1.8 / 6.1 |

### X2: X1 + `STRATA_PIPED_CONCURRENT=1` (R3)

| Phase | Aggregate tok/s | cache_n (lane 0 / 1) | TTFT s | Decode tok/s | Largest SSE gap s |
|---|---|---|---|---|---|
| Prime (cold) | n/a | 0 / 0 | 97.6 / 101.2 | 38.3 / 47.3 | 0.2 / 0.1 |
| Round 1 | 18.8 | 127,934 / 127,936 | 13.0 / 4.8 | 12.3 / 11.5 | 1.4 / 2.4 |
| Round 2 | 29.9 | 127,934 / 127,936 | 5.0 / 11.2 | 20.1 / 22.3 | 2.9 / 2.5 |
| Round 3 | 38.4 | 127,934 / 127,936 | 10.8 / 4.8 | 32.1 / 27.0 | 1.7 / 2.1 |
| Third-read writers (2048 tok) | 48.8 | 127,934 / 127,936 | 4.6 / 10.3 | 28.5 / 27.8 | **1.9 / 1.5** |
| Third cold read | n/a | n/a | **no first token** | n/a | n/a |
| Sustained | not reached | | | | |
