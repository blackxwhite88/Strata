# Strata r2 x5

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

Two live slots, 262144 maximum context, 64 GiB cache and twelve entries. Workload was about 200k per conversation, not a full 256k prompt. All twenty continuations hit; three independent cold primes took about 125–130 s each. The idle third conversation was checked before, not after, the sustained leg. Twelve entries filled and eight evictions occurred; peak use was 41.75 GiB. Sixteen entries remains untested.

## Retained tables

### Host memory probes (GB/s; FAST is 9 or more, SLOW 4.5 or less)

| When | Samples | State |
|---|---|---|
| Before launch | 9.48, 9.74, 9.55 | FAST |
| After the last request | 3.68, 3.67, 3.75 | SLOW |

### Speed

| Measure | Value | Source |
|---|---|---|
| Cold prefill, 200k, alone (3 primes) | TTFT 124.5 / 129.8 / 128.9 s; 1,610 / 1,544 / 1,555 tok/s | engine `timings`, host FAST at start |
| Decode, one warm stream alone | 62.9 tok/s (512 tokens); 61.9 (128 tokens, third conversation) | single and loss3 runs |
| Decode, two streams, rounds 1 to 3 | per stream 22.2 to 32.0 (mean 27.4); added together 54.7 mean; whole-request 40.0 (39.1 to 40.9) | 3 groups, 6 streams |
| Decode, two streams, sustained leg (5 pairs, 140 s) | per stream 19.3 to 33.7 (mean 26.5); added together 53.0 mean; whole-request 36.6 (34.8 to 38.3) | 5 groups, 10 streams |
| Warm suffix prefill (about 600 tokens) | rounds mean 191 (118 to 248); sustained mean 150 (100 to 236); alone 154 and 168 tok/s | engine `timings` |
| Restore of a parked 200k conversation | 0.40 to 1.01 s (15 restores) | engine log |
| Largest pause inside one stream | 10.0 s (sustained pair 1); typically 3 to 10 s | per-request gaps |

### Cache trace

| After | Entries (of 12) | GiB (of 64) | Evictions | Parks | Restores | MemAvailable GiB |
|---|---|---|---|---|---|---|
| launch | 0 | 0.00 | 0 | 0 | 0 | 170.1 |
| prime 1 / prime 2 | 1 / 2 | 0.22 / 3.85 | 0 | 1 / 2 | 0 | 169.5 / 165.9 |
| rounds 1 / 2 / 3 | 2 / 4 / 6 | 6.84 / 13.15 / 19.17 | 0 | 4 / 8 / 12 | 2 / 4 / 5 | 162.5 / 156.6 / 150.4 |
| prime 3 | 7 | 19.84 | 0 | 13 | 5 | 149.7 |
| loss check (pair / third) | 9 / 9 | 29.00 / 28.89 | 0 | 17 / 18 | 7 / 8 | 140.6 / 140.1 |
| single stream | 9 | 29.14 | 0 | 19 | 9 | 140.1 |
| sustained pair 1 | 12 | 38.93 | 0 | 23 | 10 | 130.8 |
| sustained pair 2 / 3 / 4 | 12 | 41.75 | 2 / 4 / 6 | 27 / 31 / 35 | 11 / 12 / 13 | 127.9 |
| sustained pair 5 and end | 12 | 41.06 | 8 | 39 | 15 | 127.9 |

### Every request

| Request | cache_n | prompt_n | TTFT s | Decode tok/s | Prefill tok/s |
|---|---|---|---|---|---|
| prime 1 (cold, alone) | 0 | 199941 | 124.5 | 55.8 | 1610 (cold) |
| prime 2 (cold, alone) | 0 | 199944 | 129.8 | 54.4 | 1544 (cold) |
| prime 3 (cold, alone) | 0 | 199944 | 128.9 | 54.2 | 1555 (cold) |
| round1 conv 1 | 199934 | 601 | 5.3 | 26.0 | 118 |
| round1 conv 2 | 199937 | 601 | 9.1 | 32.0 | 203 |
| round2 conv 1 | 199934 | 601 | 3.1 | 22.2 | 208 |
| round2 conv 2 | 199937 | 601 | 9.2 | 30.1 | 202 |
| round3 conv 1 | 199934 | 601 | 9.4 | 31.5 | 167 |
| round3 conv 2 | 199937 | 601 | 2.6 | 22.3 | 248 |
| loss check (pair) conv 2 | 199937 | 602 | 5.3 | 9.8 | 117 |
| loss check (pair) conv 1 | 199934 | 602 | 11.3 | 17.7 | 202 |
| loss check (third, alone) conv 3 | 199937 | 601 | 3.7 | 61.9 | 168 |
| single stream alone conv 1 | 199934 | 600 | 4.0 | 62.9 | 154 |
| sus1 conv 1 | 199934 | 601 | 2.8 | 19.3 | 236 |
| sus1 conv 2 | 199937 | 601 | 12.8 | 30.7 | 100 |
| sus2 conv 1 | 199934 | 601 | 12.4 | 30.3 | 102 |
| sus2 conv 2 | 199937 | 601 | 3.6 | 20.0 | 180 |
| sus3 conv 1 | 199934 | 601 | 3.4 | 21.2 | 191 |
| sus3 conv 2 | 199937 | 601 | 11.6 | 31.9 | 110 |
| sus4 conv 1 | 199934 | 601 | 11.6 | 33.0 | 110 |
| sus4 conv 2 | 199937 | 601 | 3.4 | 21.7 | 191 |
| sus5 conv 1 | 199934 | 601 | 11.5 | 33.7 | 141 |
| sus5 conv 2 | 199937 | 601 | 4.5 | 23.1 | 139 |
