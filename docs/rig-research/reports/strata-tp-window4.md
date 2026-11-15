# Strata tp window4

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

The first nominally warm pair failed reuse: one request reused 127,934 tokens and the other reused zero. Both returned 512 outputs, but that does not qualify as two warm streams. Testing stopped at the first assertion; R2 and optional spec=4 were not run. Host probes stayed FAST.

## Retained tables

### TP window 4: concurrent prefix reuse fails in FAST host state

| Phase / round | Lane 0 / lane 1 decode tok/s | Wall aggregate tok/s | Lane 0 / lane 1 TTFT s | cache_n, lane 0 / lane 1 | Host before / after, GB/s |
|---|---:|---:|---:|---:|---|
| TP spec 6 / 1, failed warm reuse | 4.33 / 38.87 | 7.91 | 6.08 / 116.36 | 127934 / 0 | FAST 9.82, 9.71, 9.87 / FAST 9.89, 9.71, 9.58 |
| R2 native | Not run | — | — | — | Not sampled |
| TP spec 4 | Not run | — | — | — | Not sampled |
