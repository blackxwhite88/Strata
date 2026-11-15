# Strata perf scout

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

Code review and interpretation of existing measurements, not a new hardware run. Corrected the early whole-request/decode confusion and identified unmatched host states. Read the later truth investigation for direct host-memory evidence.

## Retained tables

### 3. Systematic Survey & Ranking of Optimization Levers

| :---: | :--- | :--- | :---: | :---: | :---: | :---: |
| **1** | **Stage Weight Trimming (`--layer-split 23 --trim-stage-weights`)** | `src/program/generate.cpp:5067`, `5174` | **+6% to +12%** decode (+945 VRAM slots on CUDA0; frees VRAM on CUDA1) | Low | 0.5 day | No |
| **2** | **Batched MTP Drafting (`--batch-mtp` + `STRATA_PIPED_MTP=1`)** | `src/program/generate.cpp:6870-6935`, `7079` | **+15% to +20%** at 2 streams, **+5% to +8%** at 4 streams | Low | 0.5 day | No |
| **3** | **Interleaved Prompt Prefill (`STRATA_PIPED_CONCURRENT=1`)** | `docs/BATCHING.md:262-270`, `src/program/batch_read.hpp:33-55` | Eliminates 12s stalls during prompt arrival; **+4x token throughput during reads** | Medium | 1 day | No |
| **4** | **Turing SM75 Bitwise Suite (`STRATA_SM75_PERF=1`)** | `include/strata/core/sm75_series.hpp:1-15`, `src/kernels/cuda/qsa_decode_attn.cu:486` | **+5% to +12%** prefill, **+2% to +5%** decode | Very Low | 0.5 day | No |
| **6** | **Conversation Cache (`--set conversation-cache-gib=32`)** | `src/program/generate.cpp:1056` | **99.8% cache hit rate** on 32k multi-turn chat (slashes TTFT from 14.8s to 2.4s) | Low | 0.5 day | No |
| **7** | **Prefill Pipe Calibration (`--prefill-pipe 1`)** | `src/prefill/prefill.cpp:2820` | **0% to +6%** prefill on prompts near 8k multiples | Low | 0.5 day | No |
| **8** | **PCIe Share Floor (`STRATA_PCIE_MIN1=1`)** | `src/core/expert_source.cpp:5000-5006` | -2% to +2% solo, ~0% pipelined (Low priority) | Low | 0.5 day | No |
| **10** | **2MB Hugetlb Page Reservation (`vm.nr_hugepages`)** | `src/core/pinned.cu:438` | **0%** (Refuted: Arena already 100% on 2MB THP) | Low | 0.5 day | No (Not needed) |

### Detailed Arm Definitions for Validation Window:

| Arm | Objective | Command Line & Environment Diffs | Success Metric & Stop Rule |
| :---: | :--- | :--- | :--- |
| **Diag-0** | **Thermal / Clock Soak** | Log `nvidia-smi` clocks/power and CPU MHz every 1s across 3 consecutive 32k prompt runs on clean engine. | Determine if VRAM thermal throttling causes the 1.45x fast/slow gap. Stop if hardware anomaly identified. |
| **Arm C0** | **Clean Decode Baseline** | Standard upstream 0.1.59 (patch 1) baseline; test 2 streams using pure decode benchmark (fixed short prompt, 512 completion tokens). | Establish true baseline concurrent decode tok/s without prefill contamination. |
| **Arm C1** | **Stage Weight Trimming** | C0 + `--layer-split 23 --trim-stage-weights` | Confirm +945 expert slots freed on GPU 0; verify CUDA1 free VRAM > 800 MiB; target +6% to +10% decode. |
| **Arm C2** | **Piped MTP Drafting** | C1 + `--batch-mtp` + `STRATA_PIPED_MTP=1` (with `STRATA_BATCH_SELF_COMMIT` unset) | Verify log prints `2 pipelined groups draft up to 1 MTP proposal`; target **+15% to +20% concurrent decode**. |
| **Arm C3** | **Concurrent Prompt Interleaving** | C2 + `STRATA_PIPED_CONCURRENT=1` (or `STRATA_PIPED_READ_PIECE=8192`) | Stream decode stalls drop from >10s to <1s during background prompt arrival. |
| **Arm C4** | **Turing SM75 Bitwise Suite** | C3 + `STRATA_SM75_PERF=1` + `STRATA_FUSE_WAIT=2` | Target **+5% to +12% prefill speed**, +2% to +5% decode. Verify bitwise output hash equality. |
| **Arm C5** | **Prefill Pipe Calibration** | C4 + `--prefill-pipe 1` | Evens out prompt chunk boundaries; target +0% to +5% on boundary prompts. |
