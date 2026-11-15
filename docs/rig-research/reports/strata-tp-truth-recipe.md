# Strata tp truth recipe

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

Historical proposal and final recipe reduction. R2 used two live slots, a 256k ceiling and 8 GiB conversation cache. The tested final recipes in RECIPES.md retain R2 and increase budget and entry count based on subsequent cache windows. R3 is excluded after the later long-context failure.

## Retained tables

### Serving recipe decision — dual 22-GB RTX 2080 Ti / NVLink

| Intended use | Evidence / ranking | Limit |
|---|---|---|
| Rested 128k, one active | R1 wall mean 61.26; R2 60.43; production P0 57.82 tok/s | R1 and R2 are close; no paired significance estimate |
| Rested 128k, two active | R3 60.98 in one rest block; R2 58.27 across 3; R1 53.08 across 2; P0 50.97 across 2 | R3 has fewer independent blocks; its stall advantage has one valid pair only |
| Rested 200k, one active | R1 53.46 and R2 53.44; P0 49.39 tok/s | One rested block each, two groups |
| Rested 200k, two active | R2 55.64; R1 49.71; P0 48.56 tok/s | One rested block each, two groups; R2/P0 about +14.6% here only |
| Sustained 200k, two active | Final P0/R2 pair: 26.26 / 30.58 wall tok/s, +16.47% observed | Both SLOW; bandwidth means 2.980/3.245 GB/s; one pair, residual state variation; earlier R2-only 34.02 is separate |
| Incoming cold 32k beside writer | One valid R2/R3 pair: largest writer SSE gap 18.134/0.941 s | Subsequent legs censored at 120 s during FAST→SLOW; no three-pair claim |
| Four-slot 200k | Not supported in this configuration | Two 200k conversations did not fit operationally: one lane 2 tokens / length, companion re-read 200553 tokens; not a VRAM-floor rejection or established backend cause |
| TP long concurrent prompts | Reject for production on this build | Primary 128k ring error; PFHOST 128k two-card XID31;200k unqualified |

### Final Native queued cohorts

| Submitted / active slots | Replies | Wall aggregate tok/s | Per-stream decode mean [range] tok/s | TTFT median / max s | Engine prefill mean tok/s | Largest SSE gap s | Before/after memcpy GB/s |
|---|---:|---:|---:|---:|---:|---:|---:|
| 6 /2 | 6×512 | 56.83 | 34.31 [30.43,39.85] | 21.59 / 41.23 | 333.48 | 2.660 | 9.56/9.13 |
| 8 /2 | 8×512 | 52.24 | 31.27 [26.60,37.70] | 34.19 / 64.84 | 323.84 | 2.766 | 9.60/9.48 |

### Final Native four-slot 64k/128k checks

| Prompt | Wall aggregate tok/s | Per-stream decode mean [range] tok/s | TTFT median / max s | Native suffix prefill mean tok/s | Actual reused / read tokens | Before / after memcpy GB/s | Final free GPU0/1 MiB |
|---|---:|---:|---:|---:|---:|---:|---:|
| 64k | 43.71 | 12.54 [11.59,13.65] | 5.64 / 9.40 | 323.55 | [63933] / [617] | 9.64/9.26 | 530/492 |
| 128k | 21.82 | 6.23 [5.71,6.83] | 11.13 / 19.00 | 170.35 | [127934] / [617, 618, 619] | 3.81/3.78 | 534/482 |

### Final Native control pair

| Arm | Total work / final window s | Final groups / replies | Whole-wall aggregate tok/s | Group wall mean ± SD [range] tok/s | Per-stream decode mean [range] tok/s | TTFT median / max s | Native suffix prefill mean tok/s | Final boundary memcpy GB/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| P0 | 956.26 / 312.04 | 8 / 16 | 26.26 | 26.34 ± 1.26 [24.34,28.03] | 18.34 [14.48,22.91] | 10.41 / 14.57 | 98.01 | 2.92/3.04 |
| R2 | 937.77 / 301.38 | 9 / 18 | 30.58 | 30.69 ± 1.52 [28.14,32.67] | 21.95 [16.45,28.42] | 9.28 / 13.65 | 123.53 | 3.33/3.16 |

### Expert-cache counters confirm the host-memory explanation

| Phase | Expert hit mean [range] % | Explicit copied mean [range] GB per answer |
|---|---:|---:|
| Initial FAST |82.126 [80.883,83.596]|85.612 [83.329,87.388]|
| SLOW before idle |82.133 [80.894,83.596]|85.580 [83.325,87.336]|
| Recovered after idle |82.124 [80.875,83.588]|85.626 [83.377,87.414]|
