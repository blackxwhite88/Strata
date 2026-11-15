# Rig validate run

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

Historical decode-only matrix. Short-prefix C0–C5 cells used three cycles; TP had one cycle. The matrix motivated R2 stage trimming and piped MTP. Its early explanation of the fast/slow state was incomplete: later CPU-only copy measurements reproduced a real host-memory slowdown. Its recommendation of concurrent prefill is superseded by the long-context non-finite failure in the cache report. Early hardware descriptions were inconsistent.

## Retained tables

### Diag-0 Telemetry Summary

| Metric | Run 1 (Cold) | Run 2 (Warm) | Run 3 (Hot) | 10m Idle | Run 4 (Post-Idle) | Max Spread / Variance |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Prompt Tokens** | 28,171 | 28,060 | 28,049 | — | 28,258 | — |
| **Prefill Speed** | **1,661.2 tok/s** | **1,632.8 tok/s** | **1,614.1 tok/s** | — | **1,688.6 tok/s** | **4.4%** |
| **Decode Speed** | **69.9 tok/s** | **69.0 tok/s** | **62.7 tok/s** | — | **61.6 tok/s** | **11.8%** |
| **TTFT** | 16.96 s | 17.19 s | 17.38 s | — | 16.73 s | **3.8%** |
| **MTP Drafts Accepted** | 274 / 403 (68.0%) | 271 / 342 (79.2%) | 230 / 307 (74.9%) | — | 225 / 350 (64.3%) | — |
| **Peak GPU0 Temp** | 59.0°C | 63.0°C | 65.0°C | 44.0°C | 58.0°C | Max 65.0°C |
| **Peak GPU1 Temp** | 58.0°C | 63.0°C | 65.0°C | 44.0°C | 58.0°C | Max 65.0°C |
| **Peak GPU Power (W)** | 278.1 W | 239.0 W | 255.1 W | 72.8 W | 261.4 W | Within TDP limits |
| **Memory Clock (MHz)** | **6,800 MHz** | **6,800 MHz** | **6,800 MHz** | 405 MHz | **6,800 MHz** | **0.0% (Rock solid)** |
| **Throttle Reasons** | `0x4` / `0x0` | `0x4` / `0x0` | `0x4` / `0x0` | `0x1` | `0x4` / `0x0` | **Zero thermal throttle** |
| **CPU MHz (Avg)** | 1,440 MHz | 1,438 MHz | 1,442 MHz | 1,550 MHz | 1,440 MHz | Stable |

### Decode Throughput & Latency Matrix

| Arm | Description / Configuration | 1-Stream Agg Decode | 2-Stream Agg Decode | 4-Stream Agg Decode | 1-Stream Stream Decode | 2-Stream Stream Decode | 4-Stream Stream Decode | 1-Stream TTFT | 2-Stream TTFT | 4-Stream TTFT |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **C0** | Upstream 0.1.59 (patch 1) Baseline | 79.1 (±3.8) | 72.8 (±1.2) | 107.2 (±2.9) | 79.1 (±3.8) | 38.6 (±0.5) | 27.0 (±0.5) | 1.347s (±0.142s) | 2.126s (±0.178s) | 3.399s (±0.225s) |
| **C1** | Stage Weight Trimming (`split=23`) | 81.1 (±11.9) | 74.8 (±1.2) | 110.4 (±1.3) | 81.1 (±11.9) | 40.0 (±0.6) | 28.3 (±0.2) | **1.046s (±0.083s)** | **1.677s (±0.112s)** | **2.660s (±0.146s)** |
| **C2** | Piped MTP Drafting (`batch-mtp`) | 80.8 (±12.6) | **99.1 (±5.1)** | **129.0 (±4.2)** | 80.8 (±12.6) | 52.5 (±2.0) | 32.6 (±1.0) | 1.091s (±0.149s) | 1.767s (±0.197s) | 2.948s (±0.205s) |
| **C3** | Concurrent Prompt Interleaving | 80.7 (±12.7) | 98.8 (±3.3) | 127.6 (±4.6) | 80.7 (±12.7) | **55.1 (±0.9)** | **36.3 (±0.6)** | 1.165s (±0.088s) | 1.884s (±0.181s) | 3.375s (±0.276s) |
| **C4** | Turing SM75 Bitwise Suite | 79.2 (±13.0) | 98.2 (±7.6) | 123.7 (±22.7) | 79.2 (±13.0) | 54.8 (±3.1) | 34.8 (±5.7) | 1.172s (±0.134s) | 1.938s (±0.397s) | 3.923s (±1.854s) |
| **C5** | Prefill Pipe Calibration (`--prefill-pipe 1`) | 70.1 (±6.3) | 86.9 (±23.2) | 98.4 (±14.9) | 70.1 (±6.3) | 48.2 (±11.6) | 28.5 (±3.8) | 1.522s (±0.481s) | 2.599s (±1.523s) | 5.605s (±2.351s) |
| **TP** | Tensor Parallelism (Native Split Engine) | 34.3 (±0.0) | 37.3 (±0.0) | — | 34.3 (±0.0) | 17.4 (±0.0) | — | 4.912s (±0.000s) | 19.443s (±0.000s) | — |

### Prefill Throughput Matrix (Short Synthetic Prompt + Vision Enabled)

| Arm | Description | 1-Stream Prefill | 2-Stream Prefill | 4-Stream Prefill | Prefill Relative vs C0 Baseline |
|:---|:---|:---:|:---:|:---:|:---:|
| **C0** | Upstream 0.1.59 (patch 1) Baseline | 100.3 (±10.0) | 97.5 (±10.3) | 101.7 (±6.7) | 1.00x (Ref) |
| **C1** | Stage Weight Trimming | **131.2 (±8.1)** | **124.1 (±12.3)** | **129.8 (±7.1)** | **+27.6% to +30.8%** |
| **C2** | Piped MTP Drafting | 123.4 (±12.5) | 122.0 (±12.1) | 128.3 (±8.3) | +23.0% to +26.2% |
| **C3** | Concurrent Prompt Interleaving | 116.8 (±6.4) | 112.5 (±10.4) | 104.6 (±7.2) | +2.9% to +16.4% |
| **C4** | Turing SM75 Bitwise Suite | 115.1 (±9.7) | 110.9 (±17.9) | 96.2 (±33.1) | -5.4% to +14.8% |
| **C5** | Prefill Pipe Calibration | 91.6 (±33.3) | 86.2 (±56.6) | 63.7 (±32.3) | -8.7% to -37.4% (Degraded) |
| **TP** | Tensor Parallelism | 27.4 (±0.0) | 10.2 (±0.0) | — | -72.7% to -89.5% (Memory bound) |

### 6. Official Ranking of Levers

| Rank | Lever Arm | Core Flags / Environment | Measured Impact | Verdict |
|:---:|:---|:---|:---|:---:|
| **1** | **Lever 2: Piped MTP Drafting** | `--batch-mtp --set STRATA_PIPED_MTP=1 --set STRATA_BATCH_SELF_COMMIT=0` | **+32.5% to +36.1% aggregate decode**, +31.3% per-stream decode at 2 streams | **ESSENTIAL (Tier 1)** |
| **2** | **Lever 1: Stage Weight Trimming** | `--layer-split 23 --trim-stage-weights --set STRATA_STAGE_TRIM=1` | **-22% TTFT latency**, **+25% to +30% prefill**, frees +945 expert slots | **ESSENTIAL (Tier 1)** |
| **3** | **Lever 3: Concurrent Interleaving** | `--set STRATA_PIPED_CONCURRENT=1` | **+11.3% per-stream decode at 4 streams**, shields active slots from prompt stalls | **RECOMMENDED (Tier 2)** |
| **4** | **Lever 4: Turing SM75 Suite** | `--set STRATA_SM75_PERF=1 --set STRATA_FUSE_WAIT=2` | Peak burst up to 132 tok/s, bit-valid, slight spread under 4 streams | **OPT-IN (Tier 3)** |
| **5** | **Lever 5: Prefill Pipe** | `--set prefill-pipe=1` | **-11.5% to -20.5% decode collapse**, 2x TTFT degradation | **REJECT (Harmful)** |
| **6** | **Tensor Parallelism (TP)** | `--split-engine on` | Single-stream specialist; -62% aggregate decode under 2 streams | **OPT-IN (Interactive Only)** |
