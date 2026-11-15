# Strata r2 x3

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

32 GiB and eight entries preserved the two busy conversations but lost the idle third. Eighteen evictions occurred with at most 19.5 GiB used. The third cold read froze a writer for 88.3 s. Entry count, not bytes alone, governs retention.

## Retained tables

### Host memcpy probes (GB/s; FAST is 9 or more, SLOW 4.5 or less)

| When | Samples | State |
|---|---|---|
| Before | 9.32, 9.36, 9.40 | FAST |
| After | 3.12, 3.36, 3.80 | SLOW |

### Per-request results

| Phase | Aggregate tok/s | cache_n (lane 0 / 1) | TTFT s | Decode tok/s | Largest SSE gap s |
|---|---|---|---|---|---|
| Prime (cold, 512 tok) | n/a | 0 / 0 | 70.2 / 74.0 | 56.7 / 58.1 | n/a |
| Round 1 | 45.4 | 127,934 / 127,936 | 4.1 / 7.2 | 27.8 / 33.4 | 3.0 / 0.4 |
| Round 2 | 42.2 | 127,934 / 127,936 | 2.7 / 7.4 | 23.8 / 30.3 | 4.5 / 1.9 |
| Round 3 | 44.4 | 127,934 / 127,936 | 7.4 / 2.4 | 32.7 / 24.8 | 1.9 / 5.0 |
| Third-read writers (2048 tok) | 27.8 | 127,934 / 127,936 | 2.3 / 7.4 | 36.8 / 14.6 | 4.9 / **88.3** |
| Third read (cold 128k, 512 tok) | n/a | 0 (prompt 127,943) | **138.2** (queue 50.6 + read 87.6) | 39.4 | 2.1 |
| Sustained 1 | 36.8 | 127,934 / 127,936 | 9.6 / 4.9 | 28.0 / 22.3 | 0.7 / 3.5 |
| Sustained 2 | 37.8 | same | 9.0 / 3.6 | 28.2 / 21.9 | 1.7 / 5.3 |
| Sustained 3 | 38.7 | same | 9.1 / 3.6 | 29.5 / 22.5 | 1.6 / 5.3 |
| Sustained 4 | 40.3 | same | 2.8 / 8.8 | 22.6 / 30.7 | 5.9 / 1.6 |
| Sustained 5 | 40.7 | same | 8.7 / 2.8 | 31.1 / 22.9 | 1.9 / 6.1 |
| Sustained 6 | 41.2 | same | 2.8 / 8.7 | 23.2 / 31.7 | 5.8 / 1.6 |
| Sustained 7 | 42.0 | same | 3.7 / 8.9 | 24.8 / 33.0 | 5.0 / 1.5 |
| **Loss check** conv 1 / conv 2 (128 tok) | n/a | 127,934 / 127,936 | 8.7 / 2.8 | 27.0 / 11.9 | 1.5 / 5.8 |
| **Loss check** conv 3 (128 tok) | n/a | **0** (prompt 128,537) | **109.0** | 57.6 | 0.1 |

### Cache trace (`X3.cache-trace.json`)

| Point | Parked | GiB | Evictions |
|---|---|---|---|
| after both primes | 2 | 2.8 | 0 |
| after round 1 / 2 / 3 | 2 / 4 / 6 | 4.9 / 9.2 / 13.1 | 0 / 0 / 0 |
| after third-read writers | 8 | 17.4 | 1 |
| after third read | 8 | 17.9 | 2 |
| after sustained 1 / 4 / 7 | 8 / 8 / 8 | 19.3 / 18.9 / 18.8 | 3 / 9 / 15 |
| after loss check pair | 8 | 18.8 | 17 |
| end | 8 | 17.4 | 18 |
