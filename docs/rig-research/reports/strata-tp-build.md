# Strata tp build

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

Historical SM75 TP port and initial measurements. Short-prefix and microbenchmark passes established feasibility, not long-context production qualification. The early speed ranking and miss-path skip decision were revisited after state-aware long-context testing.

## Retained tables

### 1. Executive Summary & Verdicts per Stage

| Stage | Goal | Verdict | Outcome & Measured Highlights |
|---|---|---|---|
| **Stage 0: SM75 Build** | Build `strata-split-2` with `-DSTRATA_SPLIT_ARCH=75`, fix kernel bounds/shared memory limits, verify 0 host peer symbols | **PASS** | Built cleanly on SM75. All unit tests (`tests/split`) passed locally and on the rig. Zero peer symbols in base host binary. |
| **Stage 1: Kill Experiment** | Host exchange TP candidate, 36 GiB expert paging in RAM, 32K context, parallel 1 and 2 | **PASS** | Decisively beat stop rule: decode +26.3% on 4k text, +39.0% on 32k warehouse continuation, +32.7% on vision. 32K prefill achieved 1,330 tok/s (1.03x vs layer split 1,294 tok/s). |
| **Stage 2: NVLink Peer Push** | CUDA peer enablement (`cuda/peer.h`), bidirectional NVLink pattern probe, peer device mailboxes | **PASS** | Probe passed with 0 mismatches across 4 MiB and 1.9 µs flag round trips. Bit-identical greedy outputs (`ff5c270ae17ce1889861c7ed169cd64ee2ec029ae3322bb2aa84e2afbb6f36d7`). Prefill accelerated +38.4% (1,080 vs 780 tok/s); decode accelerated +35.8% on 32k continuation (127.4 vs 93.9 tok/s). |
| **Stage 3: Serving Shape** | Parallel 2 and 4, vision enabled (CPU reader), up to 128K context, dynamic arena | **PASS** | 128K context held stably on 2 lanes; 32K context held on 4 lanes. Dynamic arena lent up to 163 expert slots (0.18 GiB) smoothly under concurrent load. 28K prompt successfully joined running streams. |
| **Stage 4: Miss Path** | Cold expert CPU fallback if copy time exceeds 25% of row time | **SKIPPED** | Expert cache hit rates were 88–93%; admission token copy took 0.8–31 ms (<0.3% of row time). Did not exceed 25% threshold. |
| **Stage 5: Switch-Over** | Production shipping evaluation against layer split at 2 streams | **RECOMMENDATION: OPT-IN** | Single-stream / interactive TP is dramatically superior (+29% to +89% faster decode). However, concurrent multi-stream aggregate (-14.5% at 2 streams) and cold prompt TTFT do not meet the default production switch threshold (+15%). Keep layer-split as default; land TP as opt-in via `--split-engine on`. |

### Complete Performance Matrix

| Metric / Workload | Layer-Split (Mean) | TP Stage 1 (Host Exch, 1-lane) | TP Stage 2 (NVLink Peer, 1-lane) | TP Stage 3 (NVLink Peer, 2-lane 128k) | TP Stage 3 (NVLink Peer, 4-lane 32k) | Best TP vs LS Baseline |
|---|---|---|---|---|---|---|
| **Code Decode** (tok/s) | 76.5 | 74.0 (-3.2%) | 73.5 (-3.9%) | 73.0 (-4.6%) | 63.8 (-16.5%) | **74.0 tok/s** (parity, -3.2%) |
| **Code TTFT** (s) | 1.25 | 4.21 | 4.21 | 4.25 | 6.22 | 4.21 s (cold paging overhead) |
| **4k Text Prefill** (tok/s) | 933.2 | 780.4 (-16.4%) | **1080.4 (+15.8%)** | 973.9 (+4.4%) | 445.8 (-52.2%) | **1080.4 tok/s (+15.8%)** |
| **4k Text Decode** (tok/s) | 48.2 | 60.8 (+26.3%) | **62.2 (+29.2%)** | 48.7 (+1.1%) | 27.2 (-43.6%) | **62.2 tok/s (+29.2%)** |
| **32k Prompt Prefill** (tok/s) | 1294.0 | 1330.2 (+2.8%) | **1409.6 (+8.9%)** | 967.8 (-25.2%) | 772.1 (-40.3%) | **1409.6 tok/s (+8.9%)** |
| **32k Continuation Decode** (tok/s) | 67.5 | 93.9 (+39.0%) | **127.4 (+88.7%)** | 73.0 (+8.1%) | 46.1 (-31.7%) | **127.4 tok/s (+88.7%)** |
| **1-Image Vision Decode** (tok/s) | 46.7 | 62.0 (+32.7%) | **63.0 (+34.9%)** | 28.2 (-39.7%) | 29.2 (-37.6%) | **63.0 tok/s (+34.9%)** |
| **4-Image Vision Decode** (tok/s) | 44.9 | 61.1 (+36.1%) | **50.7 (+12.8%)** | 28.7 (-36.0%) | 27.8 (-38.1%) | **61.1 tok/s (+36.1%)** |
| **Greedy Output Hash (4k text)** | `ff5c270a...` | `ff5c270a...` | `ff5c270a...` | `ff5c270a...` | `ff5c270a...` | **Bit-Identical (100% Match)** |
| **Concurrent Aggregate** (tok/s) | 4.41 (2 streams) | N/A | N/A | 3.77 (2 streams, -14.5%) | 3.40 (4 streams, -22.8%) | 3.77 tok/s (-14.5%) |
| **Max Validated Context** | 32k (256k prod) | 32k | 32k | **128k (Full Battery)** | 32k | **128k Context** |
