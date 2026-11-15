# Strata tp truth

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

Final reduction: the host-memory slowdown reproduced in one loaded process and in a CPU-only workload. Ten minutes idle restored bandwidth and decode. The exact DIMM/controller trigger remains unproven. Properly fitting TP failed long concurrent prompts; R2 became the leading native candidate. The 200k sustained pair was one matched pair with residual state variation. Native cache budget was 8 GiB, not the originally proposed 32 GiB.

## Retained tables

### Five-repeat CPU and host-memory decision test

| Measurement | Initial fast state | Slow state | After 600 s idle |
|---|---:|---:|---:|
| Decode tok/s, n=5 | 71.260 [67.590, 72.684] | 29.557 [28.952, 30.223] | 71.552 [67.865, 73.085] |
| CPU-only memcpy GB/s, n=5 | 9.714 [9.460, 9.900] | 3.818 [3.770, 3.850] | 9.612 [9.440, 9.810] |
| CPU loop Miter/s, n=5 | 9.214 [8.590, 9.590] | 9.462 [8.780, 9.650] | 9.188 [8.830, 9.830] |
| Package temperature **during decode**, C | 44–47 | 52–53 | 44–47 |
| Mean fastest-core MHz during decode | 2990 | 2980 | 2988 |
| Core/package thermal-throttle increments | 0 | 0 | 0 |
| GPU and root-port links during decode | Gen3 x16 | Gen3 x16 | Gen3 x16 |
| GPU P-state during decode | P2 | P2 | P2 |

### Independent, synchronized transport confirmation

| Transfer | GPU 0 slow / recovered | GPU 1 slow / recovered |
|---|---:|---:|
| One card: H2D copy engine | 7.036 / 11.762 | 7.062 / 11.810 |
| One card: mapped-host GPU kernel | 5.471 / 11.231 | 5.484 / 11.268 |
| Two cards together: H2D, per card | 3.836 / 11.832 | 3.864 / 11.814 |
| Two cards together: mapped reads, per card | 2.871 / 11.052 | 2.873 / 11.089 |
| One card: GPU-local D2D | 264.349 / 264.342 | 264.718 / 264.626 |

### Decisive recovery and transport evidence (completed 11:21 UTC)

| Phase | Runs | Decode mean (tok/s) | Absolute spread | Mean expert copies / answer |
|---|---:|---:|---:|---:|
| Initial calibration | 5 | 71.183 | 5.214 | 85.61 GB |
| Slow, CPU otherwise idle | 5 | 28.373 | 1.229 | 85.59 GB |
| Slow, four additional CPU arithmetic workers | 5 | 28.369 | 1.392 | 85.80 GB |
| Immediately after standalone transport probe | 5 | 27.982 | 1.828 | 85.60 GB |
| After 600 seconds idle, **no model restart** | 5 | 71.425 | 5.231 | 85.63 GB |

### Decisive recovery and transport evidence (completed 11:21 UTC)

| Mode | GPU 0 slow / recovered (GB/s) | GPU 1 slow / recovered (GB/s) |
|---|---:|---:|
| Host to GPU, CUDA copy engine | 7.166 / 11.768 | 7.412 / 11.787 |
| GPU kernel reading mapped host RAM | 5.928 / 11.228 | 5.514 / 11.238 |
| Device-to-device on the same GPU | 264.593 / 264.483 | 264.951 / 265.060 |

### Binary and historical configuration evidence

| Binary | SHA-256 |
|---|---|
| Upstream layer split `strata` | `4f7ad93a13360398b0f97c7161c4b779c7125217e63f77a0abc0fde04add9c66` |
| TP `strata-split-2` | `6cf80765b0864557c47927249597574de8825ef3a87098ce8ab41446786d4627` |

### Completed retry and onset/recovery measurements

| Host-only load | First 60 s mean | Last 60 s mean | First report below 70% of initial-minute mean |
|---|---:|---:|---:|
| Four workers, 600 s, 40 full reports | 14.738 GB/s summed | 5.063 GB/s summed | 241 s |

### Completed retry and onset/recovery measurements

|---|---:|---:|
| RAMWatt | 123.363 W | 107.959 W |
| RAM_% | 0.000% | 0.000% |
| UncMHz | 2700 | 2700 |
| Bzy_MHz, summary of busy CPU time | 2689 | 2668 |
| PkgWatt | 32.837 W | 30.121 W |
| Package temperature | 43.13 C | 46.87 C |

### Initial recipe window: one 128k rest cycle, not a winner

| Probe-qualified FAST 128k continuation | Concurrent rounds | Per-stream emission-window rate, median | Aggregate wall-time tok/s, median | First text event, median |
|---|---:|---:|---:|---:|
| R0, 1 active | 2 | 93.46 tok/s | 56.41 | 3.65 s |
| R2, 1 active | 2 | 90.35 tok/s | 58.82 | 3.14 s |
| R0, 2 active | 2 | 36.42 tok/s | 52.35 | 4.70 s |
| R2, 2 active | 2 | 38.85 tok/s | 58.29 | 4.24 s |

### Recipe wave 1: native 128k results and the VRAM-policy decision

| Arm | Configured context / slots | 1 active | 2 active | 4 active | Minimum free MiB after warmup |
|---|---|---:|---:|---:|---:|
| R1, trim/K23 | 256k / 2 | 61.21 | 53.12 | — | 464 |
| R3, R2 plus concurrent prefill | 256k / 2 | 53.73 | 60.98 | — | 402 |
| R2-256-4 | 256k / 4 | 62.60 | 60.80 | 70.13 | 340 |
| R2-128-4 | 128k / 4 | 62.36 | 57.61 | 70.64 | 310 |
| R2, second rest cycle | 256k / 2 | 61.25 | 58.28 | — | 402 |
| R0, second rest cycle | 256k / 2 | 56.62 | 52.12 | — | 458 |

### Wave 2: first same-day production control; TP numerical guard

| 128k continuation | Wall aggregate, 1 active | Wall aggregate, 2 active |
|---|---:|---:|
| Unchanged P0, first rest cycle | 58.02 tok/s | 51.03 tok/s |
| R1, second rest cycle | 61.31 tok/s | 53.04 tok/s |
| R2, third rest cycle | 61.23 tok/s | 58.25 tok/s |

### Waves3/4: actual 200k continuations and remaining gaps

| FAST200k continuation | 1 active wall aggregate | 2 active wall aggregate | Median TTFT1/2 active |
|---|---:|---:|---:|
| P0 unchanged control |49.39|48.56|4.40/5.47s|
| R1 |53.46|49.71|3.87/4.97s|
| R2 |53.44|55.64|3.87/5.26s|

### Proper-fit TP128k result and XID31 abort

| Correctness case | Observed result |
|---|---|
| Primary64k cold beside2048-token writer | completed2048+512 tokens |
| Primary128k cold beside writer | `prefill: ring error2`, stopped-engine SSE error; no qualified completion |
| PFHOST64k | completed2048+512 tokens |
| PFHOST128k | two-card XID31 MMU virtual-write faults, safety abort |

### Corrected stall pair and budget censoring

| Attempt | Before/after memcpyGB/s | Completed usage observations | Disposition |
|---|---|---|---|
| R3 rep1 |9.00/3.80|companion512,cold512;active final usage unavailable|active request censored at 120s|
| R2 rep1 |9.24/3.72|companion512;active/cold final usage unavailable|active and cold censored at 120s|

### Final reduction: initial five-repeat matrix

| Configuration / task | Groups | Decode mean [min,max] tok/s | TTFT mean [min,max] s | Native prefill mean tok/s | Reused token range |
|---|---:|---:|---:|---:|---:|
| TP-32k-b1-p1-r36 / code / 1 stream | 5 | 35.34 [31.31,42.61] | 12.58 [4.49,15.45] | 14.44 | 0–0 |
| TP-32k-b1-p1-r36 / validation-code / 1 stream | 5 | 37.94 [33.73,43.79] | 10.34 [6.47,15.00] | 14.38 | 0–0 |
| TP-32k-b2-p1-r36 / code / 1 stream | 5 | 31.15 [30.44,32.05] | 15.19 [14.76,15.57] | 9.48 | 0–0 |
| TP-32k-b2-p1-r36 / validation-code / 1 stream | 5 | 34.13 [32.66,36.03] | 14.41 [12.82,15.52] | 9.16 | 0–0 |
| LS-32k-b1 / code / 1 stream | 5 | 25.62 [21.77,33.49] | 2.44 [2.18,2.94] | 60.22 | 0–0 |
| LS-32k-b1 / 4k / 1 stream | 5 | 34.63 [30.84,41.23] | 6.89 [6.25,7.29] | 588.12 | 0–0 |
| LS-32k-b1 / 32k / 1 stream | 5 | 29.55 [25.43,31.52] | 8.52 [2.07,29.79] | 332.24 | 0–32101 |
| LS-32k-b1 / image / 1 stream | 5 | 30.99 [29.47,32.86] | 2.81 [2.39,3.48] | 75.46 | 0–0 |
| TP-32k-b1-p0-r36 / code / 1 stream | 5 | 28.49 [26.99,29.28] | 17.34 [17.05,18.00] | 8.30 | 0–0 |
| TP-32k-b1-p0-r36 / 4k / 1 stream | 5 | 31.65 [28.41,34.97] | 13.68 [13.30,14.35] | 295.88 | 0–0 |
| TP-32k-b1-p0-r36 / 32k / 1 stream | 5 | 30.91 [29.72,32.50] | 23.73 [13.87,30.90] | 20.56 | 31583–32101 |
| TP-32k-b1-p0-r36 / image / 1 stream | 5 | 28.99 [21.84,33.85] | 18.79 [18.38,19.41] | 10.44 | 0–0 |

### Final reduction: Native FAST long continuations

| Arm / prompt / active | Groups / rest blocks | Wall aggregate mean [range] tok/s | Per-stream decode mean [range] tok/s | TTFT mean [range] s | Native prefill mean tok/s |
|---|---:|---:|---:|---:|---:|
| P0 / 128k / 1 | 4 / 2 | 57.82 [51.37,63.86] | 93.05 [88.25,96.99] | 3.45 [2.74,4.18] | 192.55 |
| P0 / 128k / 2 | 4 / 2 | 50.97 [48.81,53.20] | 34.35 [28.99,38.86] | 4.97 [2.82,7.80] | 201.60 |
| P0 / 200k / 1 | 2 / 1 | 49.39 [44.89,53.88] | 84.56 [81.87,87.26] | 4.40 [3.64,5.16] | 149.65 |
| P0 / 200k / 2 | 2 / 1 | 48.56 [48.28,48.85] | 33.31 [29.27,37.46] | 5.48 [3.40,7.57] | 189.35 |
| R0 / 128k / 1 | 4 / 2 | 56.52 [52.02,61.23] | 93.63 [89.70,97.91] | 3.65 [3.14,4.15] | 177.05 |
| R0 / 128k / 2 | 4 / 2 | 52.24 [50.10,54.58] | 35.79 [29.91,40.74] | 5.05 [2.91,7.88] | 199.00 |
| R1 / 128k / 1 | 4 / 2 | 61.26 [54.98,67.63] | 96.22 [93.55,98.73] | 3.13 [2.39,3.88] | 215.38 |
| R1 / 128k / 2 | 4 / 2 | 53.08 [50.65,55.44] | 35.02 [29.74,39.32] | 4.47 [2.47,7.17] | 227.94 |
| R1 / 200k / 1 | 2 / 1 | 53.46 [47.08,59.85] | 87.54 [85.62,89.45] | 3.87 [2.84,4.91] | 178.90 |
| R1 / 200k / 2 | 2 / 1 | 49.71 [48.85,50.56] | 33.57 [29.38,37.69] | 5.10 [3.07,7.39] | 207.07 |
| R2 / 128k / 1 | 6 / 3 | 60.43 [52.72,67.99] | 94.24 [87.44,99.67] | 3.14 [2.40,3.88] | 214.90 |
| R2 / 128k / 2 | 6 / 3 | 58.27 [57.92,58.65] | 38.85 [34.27,43.61] | 4.21 [2.45,5.95] | 251.95 |
| R2 / 200k / 1 | 2 / 1 | 53.44 [47.20,59.68] | 87.52 [85.70,89.35] | 3.87 [2.86,4.88] | 178.35 |
| R2 / 200k / 2 | 2 / 1 | 55.64 [55.35,55.92] | 39.61 [33.13,45.61] | 5.17 [2.96,7.18] | 214.65 |
| R2-128-4 / 128k / 1 | 1 / 1 | 62.36 [62.36,62.36] | 90.65 [90.65,90.65] | 2.57 [2.57,2.57] | 249.30 |
| R2-128-4 / 128k / 2 | 1 / 1 | 57.61 [57.61,57.61] | 40.88 [33.69,48.07] | 4.85 [2.55,7.14] | 215.70 |
| R2-128-4 / 128k / 4 | 1 / 1 | 70.64 [70.64,70.64] | 24.27 [19.55,30.15] | 7.28 [2.65,12.04] | 254.93 |
| R2-256-4 / 128k / 1 | 1 / 1 | 62.60 [62.60,62.60] | 92.63 [92.63,92.63] | 2.66 [2.66,2.66] | 241.20 |
| R2-256-4 / 128k / 2 | 1 / 1 | 60.80 [60.80,60.80] | 42.06 [36.01,48.10] | 4.41 [2.60,6.21] | 236.85 |
| R2-256-4 / 128k / 4 | 1 / 1 | 70.13 [70.13,70.13] | 24.23 [19.46,30.23] | 7.43 [2.74,12.30] | 247.88 |
| R3 / 128k / 1 | 2 / 1 | 53.73 [50.32,57.14] | 81.61 [80.56,82.65] | 3.30 [2.78,3.83] | 197.50 |
| R3 / 128k / 2 | 2 / 1 | 60.98 [60.76,61.19] | 45.26 [43.16,47.37] | 4.24 [2.53,5.94] | 242.85 |

### Cold ingestion is a different cost

| Arm / prefix | Cold setup samples | Tokens actually read | TTFT observed s | Engine prefill observed tok/s |
|---|---:|---:|---:|---:|
| R0 /128k |2|127941|69.45–71.42|1797.2–1847.3|
| R1 /128k |2|127941|70.45–71.23|1801.0–1821.0|
| R2 /128k |3|127941|70.85–71.39|1796.7–1810.3|
| R3 /128k |1|127941|70.58|1817.7|
| P0 /128k |3|127941|72.13–72.81|1762.8–1778.5|
| R1 /200k |1|199941|125.49|1596.8|
| R2 /200k |1|199941|126.15|1588.3|
| P0 /200k |1|199941|127.67|1569.4|

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
