# Rig night run

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

Historical nine-arm battery. The concurrency column includes prompt read time; it is whole-request throughput, not isolated decode. The identical A1/A4 configurations ran in different host states. The weighted ranking and attribution of regressions are superseded by the later state investigation. Early hardware descriptions were inconsistent; use the hardware record in the main research README.

## Retained tables

### 2. Comprehensive Benchmark Results Table

| Arm ID | Configuration Summary | Par | Code TTFT (s) | 4k PF (t/s) | 32k Cont TTFT (s) | 32k Hit (%) | 128k PF (t/s) | 128k Needle | 1-Img TTFT (s) | 4-Img TTFT (s) | Agg Dec (t/s) | CUDA1 Free |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A0_prod | Production Baseline (0.1.55, 256k int8, MTP-3, par=2) | 2 | 2.20 ± 0.13 | 571.7 ± 2.5 | 2.42 ± 0.83 | 99.8% | 1022.9 ± 85.5 | 3/3 (100%) | 5.71 ± 6.20 | 10.65 ± 8.46 | 10.5 ± 1.6 | 220 MiB |
| A1 | Upstream 0.1.59 (patch 1) Baseline (128k int8, MTP-3, par=2) | 2 | 1.32 ± 0.08 | 939.1 ± 9.0 | 1.33 ± 1.42 | 99.3% | 1675.4 ± 33.0 | 3/3 (100%) | 2.37 ± 1.46 | 3.78 ± 0.26 | 12.6 ± 0.7 | 464 MiB |
| A2 | A1 + Native IQ SM75 Kernels (6dbafa61 cherry-pick, par=2) | 2 | 1.38 ± 0.20 | 635.7 ± 83.6 | 2.14 ± 0.92 | 99.8% | 1118.4 ± 88.5 | 3/3 (100%) | 4.95 ± 5.91 | 9.77 ± 7.74 | 10.8 ± 1.8 | 462 MiB |
| A3 | A1 + SIMT Opt-Ins (SELECT_SIMT=2, PA_V2T=1, par=2) | 2 | 2.01 ± 0.14 | 609.1 ± 3.6 | 2.36 ± 0.83 | 99.8% | 1219.9 ± 45.8 | 3/3 (100%) | 5.14 ± 5.09 | 9.90 ± 7.26 | 10.9 ± 2.0 | 462 MiB |
| A4 | Drafting A/B: Upstream MTP Baseline (spec=3, par=2) | 2 | 1.31 ± 0.06 | 792.6 ± 318.6 | 2.38 ± 0.71 | 99.8% | 1132.7 ± 46.2 | 3/3 (100%) | 4.59 ± 5.14 | 9.29 ± 8.34 | 11.4 ± 1.2 | 462 MiB |
| A5 | Drafting A/B: DFlash2 Candidate (spec=6, draft-conf=0.5, par=2) | 2 | 1.64 ± 0.41 | 613.2 ± 8.5 | 2.53 ± 0.76 | 99.3% | 1134.7 ± 78.7 | 3/3 (100%) | 4.97 ± 4.74 | 10.19 ± 7.57 | 10.3 ± 1.0 | 412 MiB |
| A6 | Recipe B: 4-stream 128k int8 (MTP-3, par=4) | 4 | 2.22 ± 0.05 | 586.5 ± 2.2 | 2.54 ± 1.03 | 99.8% | 993.5 ± 31.2 | 3/3 (100%) | 5.84 ± 5.22 | 11.08 ± 8.64 | 10.4 ± 1.8 | 450 MiB |
| A7 | Recipe A: 4-stream 256k q4_0 KV (MTP-3, par=4) | 4 | 2.30 ± 0.11 | 486.1 ± 80.4 | 2.63 ± 1.03 | 99.8% | 882.7 ± 30.8 | 3/3 (100%) | 5.92 ± 4.96 | 10.23 ± 8.66 | 10.1 ± 1.3 | 448 MiB |
| A8 | Recipe C: 2-stream 256k int8 + 32GB Host Cache (MTP-3, par=2) | 2 | 1.98 ± 0.16 | 552.5 ± 85.6 | 2.42 ± 0.65 | 99.8% | 1099.8 ± 36.6 | 3/3 (100%) | 5.11 ± 5.70 | 9.53 ± 8.90 | 10.9 ± 1.5 | 456 MiB |

### Detailed Decode Throughput Breakdown (tok/s)

| Arm ID | Code Dec (t/s) | 4k Text Dec (t/s) | 32k Cont Dec (t/s) | 128k Dec (t/s) | 1-Img Dec (t/s) | 4-Img Dec (t/s) | Concurrent Per-Stream Decode (t/s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A0_prod | 39.3 ± 18.1 | 16.0 ± 9.6 | 41.1 ± 5.1 | 24.5 ± 13.1 | 35.8 ± 15.4 | 38.8 ± 4.9 | [1.1, 40.5] |
| A1 | 76.3 ± 16.3 | 45.8 ± 14.5 | 72.9 ± 8.6 | 55.8 ± 15.9 | 65.3 ± 11.2 | 68.5 ± 0.9 | [1.4, 45.9] |
| A2 | 60.0 ± 12.6 | 16.4 ± 8.5 | 44.0 ± 9.9 | 22.2 ± 12.1 | 38.2 ± 16.2 | 40.5 ± 5.7 | [1.2, 40.2] |
| A3 | 41.5 ± 21.0 | 16.9 ± 9.4 | 49.0 ± 12.1 | 23.5 ± 13.7 | 38.4 ± 15.7 | 40.8 ± 5.9 | [1.2, 41.7] |
| A4 | 75.5 ± 14.4 | 27.9 ± 40.7 | 46.5 ± 8.7 | 21.6 ± 10.9 | 38.4 ± 11.2 | 39.9 ± 5.4 | [1.3, 39.6] |
| A5 | 55.9 ± 8.1 | 13.8 ± 6.5 | 46.1 ± 3.0 | 20.1 ± 2.6 | 33.2 ± 10.8 | 35.8 ± 4.7 | [1.1, 39.6] |
| A6 | 38.6 ± 18.5 | 15.6 ± 6.4 | 43.3 ± 5.5 | 20.7 ± 11.7 | 35.4 ± 11.8 | 35.1 ± 3.3 | [0.9, 5.0, 3.5, 3.5] |
| A7 | 36.7 ± 16.5 | 14.4 ± 6.7 | 44.1 ± 14.6 | 23.6 ± 14.3 | 32.2 ± 16.3 | 32.3 ± 2.3 | [2.5, 4.5, 3.3, 3.8] |
| A8 | 38.7 ± 17.7 | 15.1 ± 7.0 | 44.1 ± 2.1 | 20.8 ± 11.6 | 35.5 ± 9.4 | 38.7 ± 6.7 | [1.2, 41.1] |

### VRAM Allocation & Thermal Headroom

| Arm ID | GPU 0 Used (MiB) | GPU 0 Free (MiB) | GPU 1 Used (MiB) | GPU 1 Free (MiB) | GPU 0 Temp (°C) | GPU 1 Temp (°C) | Thermal Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A0_prod | 21404 | 596 | 21782 | 220 | 70 | 67 | Optimal (<75°C) |
| A1 | 21408 | 592 | 21538 | 464 | 69 | 66 | Optimal (<75°C) |
| A2 | 21414 | 586 | 21540 | 462 | 70 | 66 | Optimal (<75°C) |
| A3 | 21414 | 586 | 21540 | 462 | 70 | 67 | Optimal (<75°C) |
| A4 | 21414 | 586 | 21540 | 462 | 70 | 66 | Optimal (<75°C) |
| A5 | 21460 | 540 | 21590 | 412 | 70 | 67 | Optimal (<75°C) |
| A6 | 21430 | 570 | 21552 | 450 | 73 | 67 | Optimal (<75°C) |
| A7 | 21434 | 566 | 21554 | 448 | 72 | 65 | Optimal (<75°C) |
| A8 | 21420 | 580 | 21546 | 456 | 70 | 66 | Optimal (<75°C) |

### 3. Weighted Ranking Analysis

| Rank | Arm ID | Configuration | Concurrent Decode (40%) | 128k Prefill (30%) | Stability & VRAM (20%) | Simplicity (10%) | Weighted Total (100) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A1 | Upstream 0.1.59 (patch 1) Baseline (128k int8, MTP-3, par=2) | 40.0 / 40 (12.6 t/s) | 30.0 / 30 (1675.4 t/s) | 19.3 / 20 (464 MiB free) | 10.0 / 10 | **99.3** |
| 2 | A4 | Drafting A/B: Upstream MTP Baseline (spec=3, par=2) | 36.0 / 40 (11.4 t/s) | 20.3 / 30 (1132.7 t/s) | 19.2 / 20 (462 MiB free) | 10.0 / 10 | **85.5** |
| 3 | A8 | Recipe C: 2-stream 256k int8 + 32GB Host Cache (MTP-3, par=2) | 34.6 / 40 (10.9 t/s) | 19.7 / 30 (1099.8 t/s) | 19.1 / 20 (456 MiB free) | 9.0 / 10 | **82.4** |
| 4 | A3 | A1 + SIMT Opt-Ins (SELECT_SIMT=2, PA_V2T=1, par=2) | 34.6 / 40 (10.9 t/s) | 21.8 / 30 (1219.9 t/s) | 19.2 / 20 (462 MiB free) | 6.0 / 10 | **81.7** |
| 5 | A2 | A1 + Native IQ SM75 Kernels (6dbafa61 cherry-pick, par=2) | 34.3 / 40 (10.8 t/s) | 20.0 / 30 (1118.4 t/s) | 19.2 / 20 (462 MiB free) | 6.0 / 10 | **79.5** |
| 6 | A6 | Recipe B: 4-stream 128k int8 (MTP-3, par=4) | 32.9 / 40 (10.4 t/s) | 17.8 / 30 (993.5 t/s) | 19.0 / 20 (450 MiB free) | 9.0 / 10 | **78.7** |
| 7 | A5 | Drafting A/B: DFlash2 Candidate (spec=6, draft-conf=0.5, par=2) | 32.7 / 40 (10.3 t/s) | 20.3 / 30 (1134.7 t/s) | 18.2 / 20 (412 MiB free) | 6.0 / 10 | **77.2** |
| 8 | A0_prod | Production Baseline (0.1.55, 256k int8, MTP-3, par=2) | 33.1 / 40 (10.5 t/s) | 18.3 / 30 (1022.9 t/s) | 14.4 / 20 (220 MiB free) | 10.0 / 10 | **75.9** |
| 9 | A7 | Recipe A: 4-stream 256k q4_0 KV (MTP-3, par=4) | 32.0 / 40 (10.1 t/s) | 15.8 / 30 (882.7 t/s) | 19.0 / 20 (448 MiB free) | 9.0 / 10 | **75.7** |
