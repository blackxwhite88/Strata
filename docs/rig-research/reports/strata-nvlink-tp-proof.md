# Strata nvlink tp proof

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

Hardware microbenchmarks established fast peer transport and the SM75 shared-memory limit. These are not end-to-end serving speedups. The 16-column recurrence fits the 64 KiB per-block limit; the 32-column implementation does not.

## Retained tables

### 2.2 Quantization & Memory Footprint Comparison

| Format / Representation | Bytes / Block | Weights / Block | Bits / Weight | Total Routed Bytes | Total Routed GiB | GiB / Card (TP=2) |
|---|---|---|---|---|---|---|
| **Ideal 4-bit (pure nibble)** | 16 B | 32 | 4.00 | 60,397,977,600 B | 56.2500 GiB | **28.1250 GiB** |
| **Target: Qwen3.8-Flash-Next Heretic IQ4_XS** | 136 B | 256 | 4.25 | 64,172,851,200 B | 59.7656 GiB | **29.8828 GiB** |
| **Q4_0 (Expanded from Q2_0)** | 18 B | 32 | 4.50 | 67,947,724,800 B | 63.2812 GiB | **31.6406 GiB** |

### 2.3 Per-Card VRAM Balance Sheet (Dual RTX 2080 Ti 22 GB)

| Component | Size (Total) | Per Card (TP=2) | Notes / Source |
|---|---|---|---|
| **Routed Experts (Qwen3.8-Flash-Next Heretic IQ4_XS)** | 59.77 GiB | **29.88 GiB** | Sharded column/row across 2 cards |
| **Dense Weights (Embed, Heads, GDN, Attn)** | 3.68 GiB | **1.84 GiB** | Sharded or replicated dense layers |
| **KV Cache (@ 32K context, FP16)** | 3.00 GiB | **1.50 GiB** | 12 attention layers $\times$ 32K tokens |
| **KV Cache (@ 128K context, FP16)** | 12.00 GiB | **6.00 GiB** | Qualified TP limit in `src/split` |
| **Prefill Workspace Scratch** | 4.00 GiB | **2.00 GiB** | Activation scratch & temporary tiles |
| **Communication Buffers (Peer Ring / Direct)** | 0.20 GiB | **0.10 GiB** | P2P ring buffers & slot flags |
| **Total Required for All-Resident (32K)** | **70.65 GiB** | **35.32 GiB** | **Deficit: -13.72 GiB per card** |
| **Total Required for All-Resident (128K)** | **79.65 GiB** | **39.82 GiB** | **Deficit: -18.22 GiB per card** |

### 4.2 Numerical Equivalence Validation (Offline Simulation)

| Sequence Length $T$ | 16-col vs 32-col Output $y$ Diff | 16-col vs 32-col State $S$ Diff | 16-col vs Serial Output $y$ Diff | 16-col vs Serial State $S$ Diff | Verdict |
|---|---|---|---|---|---|
| $T = 1$ | $0.00e+00$ | $0.00e+00$ | $2.59 \times 10^{-7}$ | $0.00e+00$ | **Bit-Identical** |
| $T = 16$ | $0.00e+00$ | $0.00e+00$ | $3.34 \times 10^{-7}$ | $1.39 \times 10^{-7}$ | **Bit-Identical** |
| $T = 32$ | $0.00e+00$ | $0.00e+00$ | $4.39 \times 10^{-7}$ | $3.42 \times 10^{-7}$ | **Bit-Identical** |
| $T = 48$ | $0.00e+00$ | $0.00e+00$ | $4.70 \times 10^{-7}$ | $2.03 \times 10^{-7}$ | **Bit-Identical** |
| $T = 64$ | $0.00e+00$ | $0.00e+00$ | $4.65 \times 10^{-7}$ | $2.93 \times 10^{-7}$ | **Bit-Identical** |
| $T = 128$ | $0.00e+00$ | $0.00e+00$ | $4.64 \times 10^{-7}$ | $4.18 \times 10^{-7}$ | **Bit-Identical** |

### 5.2 Standalone Peer Reduction Measured Benchmark

| Tokens $T$ | Wire Size (FP32) | Wire Size (FP16) | Host Transport Latency | Host Transport Bandwidth | sFNX Peer Ring Latency | sFNX Peer Ring Bandwidth | Exact Peer Direct Latency | Exact Peer Direct Bandwidth | Speedup over Host |
|---|---|---|---|---|---|---|---|---|---|
| **$T = 1$** | 0.01 MiB | 5.0 KiB | **15.4 $\mu s$** | 1.3 GB/s | **9.2 $\mu s$** | 2.2 GB/s | **12.3 $\mu s$** | 1.7 GB/s | **1.67x** |
| **$T = 16$** | 0.16 MiB | 80.0 KiB | **40.0 $\mu s$** | 8.2 GB/s | **12.8 $\mu s$** | 25.6 GB/s | **15.0 $\mu s$** | 21.9 GB/s | **3.13x** |
| **$T = 1024$** | 10.00 MiB | 5.00 MiB | **1,737.6 $\mu s$** | 12.1 GB/s | **305.5 $\mu s$** | 68.6 GB/s | **279.9 $\mu s$** | 74.9 GB/s | **6.21x** |
| **$T = 4096$** | 40.00 MiB | 20.00 MiB | **6,915.0 $\mu s$** | 12.1 GB/s | **1,219.6 $\mu s$** | 68.8 GB/s | **1,083.0 $\mu s$** | 77.5 GB/s | **6.38x** |
| **$T = 5$** (odd) | 0.05 MiB | 25.0 KiB | **16.5 $\mu s$** | 6.2 GB/s | **7.7 $\mu s$** | 13.2 GB/s | **10.3 $\mu s$** | 9.9 GB/s | **2.14x** |
| **$T = 17$** (odd) | 0.17 MiB | 85.0 KiB | **40.6 $\mu s$** | 8.6 GB/s | **10.9 $\mu s$** | 32.0 GB/s | **13.2 $\mu s$** | 26.5 GB/s | **3.72x** |
| **$T = 1025$** (odd)| 10.01 MiB | 5.00 MiB | **1,738.7 $\mu s$** | 12.1 GB/s | **305.9 $\mu s$** | 68.6 GB/s | **280.4 $\mu s$** | 74.9 GB/s | **6.20x** |
| **$T = 4097$** (odd)| 40.01 MiB | 20.01 MiB | **6,919.0 $\mu s$** | 12.1 GB/s | **1,219.8 $\mu s$** | 68.8 GB/s | **1,083.2 $\mu s$** | 77.5 GB/s | **6.38x** |

### Test 2: Numerical Agreement & Kernel Latency

| Tokens $T$ | Serial Kernel Latency | 16-Col Chunked Kernel Latency | Relative Output Diff ($y_{rel}$) | Relative State Diff ($S_{rel}$) | Agreement Status |
|---|---|---|---|---|---|
| **$T = 1$** | **47.78 $\mu s$** | 106.50 $\mu s$ | $2.93 \times 10^{-7}$ | $1.74 \times 10^{-7}$ | **PASS (FP32 match)** |
| **$T = 16$** | **24.64 $\mu s$** | 58.75 $\mu s$ | $3.01 \times 10^{-6}$ | $3.33 \times 10^{-6}$ | **PASS (FP32 match)** |
| **$T = 32$** | **36.70 $\mu s$** | 59.36 $\mu s$ | $7.97 \times 10^{-6}$ | $7.87 \times 10^{-6}$ | **PASS (FP32 match)** |
| **$T = 64$** | **61.44 $\mu s$** | 76.54 $\mu s$ | $1.63 \times 10^{-5}$ | $1.59 \times 10^{-5}$ | **PASS (FP32 match)** |
| **$T = 128$** | 120.38 $\mu s$ | **112.77 $\mu s$** | $0.00 \times 10^{+0}$ | $0.00 \times 10^{+0}$ | **PASS (Bit-Identical)** |
| **$T = 512$** | 435.90 $\mu s$ | **331.74 $\mu s$** | $0.00 \times 10^{+0}$ | $0.00 \times 10^{+0}$ | **PASS (Bit-Identical)** |
| **$T = 1024$**| 856.80 $\mu s$ | **662.78 $\mu s$** | $0.00 \times 10^{+0}$ | $0.00 \times 10^{+0}$ | **PASS (Bit-Identical)** |

### 6.3 Implementation Roadmap & Effort Estimates

| Stage | Milestone | Scope / Deliverables | Effort Estimate | Status |
|---|---|---|---|---|
| **Stage 1** | **Bounded Proof (Recurrence & Peer Transport)** | SM75 shared memory kernel fix, standalone synthetic NVLink peer harness, memory arithmetic, rig validation. | 1 engineer-week | **COMPLETE (This PR)** |
| **Stage 2** | **Split Engine NVLink Peer Transport + Expert Paging** | 1. Replace host transport in `src/split` with NVLink peer ring.<br>2. Wire `FNX_EXPERT_RAM_GIB` dynamic expert cache into `strata-split-2`.<br>3. Validate short-context serving (4K–32K) on dual RTX 2080 Ti. | 1.5 – 2 engineer-weeks | Ready to begin |
| **Stage 3** | **Long-Context (128K/256K) Qualification & Benchmark** | 1. KV cache sizing & quantization for 128K context.<br>2. Multi-lane scheduling & MTP draft rollback qualification.<br>3. A/B benchmark against production layer-split service. | 2 – 3 engineer-weeks | Post-Stage 2 |
