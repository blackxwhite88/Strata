# Strata perf review

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

Independent review of existing measurements. Identical A1/A4 arms exposed uncontrolled host state. It also identified prompt-inclusive throughput labelled as decode. Advice and proposed checks are not new hardware results.

## Retained tables

### 2. Scout claims, checked

| Claim | Verdict | Evidence |
| --- | --- | --- |
| Overnight aggregate divides by wall time including a 32K prefill | **Correct** | `rig-night/bench_battery.py:401-438` |
| Expert arena is on 4 KB pages | **Wrong** | Engine log says `transparent huge pages requested (MADV_HUGEPAGE)`; pid 471220 has `AnonHugePages: 59125760 kB` = 56.39 GiB, the whole arena. `src/core/pinned.cu:457-510` is the THP fallback the scout did not read |
| `STRATA_PIPED_MTP=2` alone restores drafting | **Wrong as written** | Needs `--batch-mtp` too (`generate.cpp:6927`), and is refused while `STRATA_BATCH_SELF_COMMIT=1` is set (`generate.cpp:7079`), which production sets |
| Drafting "doubles" concurrent decode | **Overstated** | Upstream measured +15 to +20% at 2 streams, +5 to +8% at 4 (`docs/BATCHING.md:500-513`) |
| PCIe share truncates to 0 | **Correct**, detail off | `expert_source.cpp:5001`; with `pcie_num` 84 it is 0 for 3 misses or fewer, not "fewer than 3" |
| `STRATA_SM75_PERF` is opt-in and unset | **Correct** | `sm75_series.hpp:3-7`. But `STRATA_BF16_TC=1` is not part of it (`sm75_series.hpp:13-15`) and production already sets it |
| `--prefill auto:2048` shrinks chunks | **Wrong** | `auto:N` can only raise the ceiling; below 16384 it means 8192 (`generate.cpp:3585-3587`). It changes nothing |
| `--layer-split 23` trims CUDA0's dense weights | **Incomplete** | Needs `--trim-stage-weights` or `STRATA_STAGE_TRIM=1` as well (`generate.cpp:5067`, `5174`) |
| Peer-device stages rows through host RAM | **Correct for decode** | `peer_experts.cpp:297-301`. P2P exists but only the prefill path uses it (`prefill.cpp:2593-2607`) |
| Production environment has 6 variables | **Incomplete** | It has 16, including the batch switches that block piped drafting |
| Upstream 0.1.59 (patch 1) is +70 to +186% over production | **Not shown** | Fast-state A1 against slow-state A0. In the slow state the two builds are level (section 5) |
| SM75 native IQ kernels regress prefill 33% (A2) | **Not shown** | A2 (1168 tok/s, 39.9 decode) equals same-config rerun A4 (1200, 42.9) |
