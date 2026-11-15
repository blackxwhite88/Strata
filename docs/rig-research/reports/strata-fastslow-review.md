# Strata fastslow review

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

Read-only interpretation of existing transport and decode observations. Both cards shared the SLOW host cap; GPU-local copies stayed unchanged. Memory-path throttling and a CPU clamp were proposed alternatives. The later truth investigation measured stable CPU loops/clocks and reproduced the CPU-memory drop.

## Retained tables

### Evidence this rests on

| UTC | Step | Decode tok/s | TTFT s |
|---|---|---|---|
| 10:52:35–10:55:13 | first 11 requests after load | 55–81 | 3.8–6.3 (27 for the 32k prompt) |
| 10:55:14–10:56:27 | next 3 requests | 47 → 35 → 36 | 9.9–18 |
| 10:56:28–11:08:22 | 20 requests, incl. the 4-thread CPU spinner pairs | 27–29 | 16–25 uncached |
| 11:08:23–11:18:27 | idle 600 s, model kept loaded | | |
| 11:18:28–11:19:27 | 5 requests | 68–73 | 4.6–4.9 |

### Evidence this rests on

| Mode | Slow, one card | Slow, both at once | Fast, one card | Fast, both at once |
|---|---|---|---|---|
| `cudaMemcpyAsync` host→GPU | 7.17 / 7.41 | 3.75 + 3.81 | 11.77 / 11.79 | 11.77 + 11.78 |
| GPU kernel reading mapped host memory | 5.93 / 5.51 | 2.73 (GPU 0) | 11.23 / 11.24 | 11.06 + 11.07 |
| GPU→GPU same card | 264 | 264 | 264 | 264 |

### Ranked explanations

| # | Explanation | For | Against | Cheapest decisive measurement |
|---|---|---|---|---|
| 1 | **Memory throttling.** The memory controller cuts DIMM bandwidth after minutes of heavy reads (temperature-based, or the activity-based kind that needs no sensor). | Shared cap across cards. Onset needs sustained traffic; rest cures it. CPU spinner did not help. CPU thermal counters 0. GPU memory unaffected. 8 hot-running 32 GB DDR3 RDIMMs, 2 per channel, beside two 200 W cards. New processes inherit it. | Not observed directly. BIOS may have throttling off. No DIMM temperature is readable without root. | Host probe in both states: `memcpy_GB_s` falls, `loop_Mit_s` and `top4_MHz` do not. |
| 2 | **CPU package clamped to 1.2 GHz** by the board (VRM over-temperature asserting PROCHOT, a known weak spot of this board family), dragging the uncore and its I/O block down. | Shared cap. 3.0/1.2 = 2.5× matches 72/28 = 2.6×. Spinner cannot lift a clamp. TTFT also 3.6× worse. The kernel's counters may not count an *external* PROCHOT (from memory; verify). | CPU package only 47–49 C and lightly loaded, so the VRM has little reason to overheat. Slow level is flat for 12 minutes; a clamp usually oscillates. | Same probe: `loop_Mit_s` falls to ~40% and `top4_MHz` ≈ 1200. |
| 4 | **PCIe link dropped** to Gen2 or Gen1 on both cards (driver power management or retraining). | Driver does move link speed (Gen1 at idle). Slow rates sit near Gen2 x16 (8 GB/s raw) and Gen1 x16 (4 GB/s raw). | Needs *both* links to change speed between the single and parallel passes. 7.2–7.4 and 3.8 GB/s would be 90–95% of raw, while the fast state reaches only 75% of Gen3 raw. AER counters 0. Width is x16. | Two more columns in the 1 Hz sample: `pcie.link.gen.current,pcie.link.width.current`. Cheapest of all; do it first. |
| 5 | **GPU-side hidden throttle** (memory-junction or VRM temperature, power cap, P-state). | Heat-like timing. Junction temperature is not exposed on a 2080 Ti. | Per-card cause cannot give a shared cap. GPU→GPU copy steady at 264 GB/s. Clocks and the 0x4 bit are identical in both states. Core temps 68–73 C. | Probe arm B below (GPU heat without host traffic). |
| 6 | **THP compaction, khugepaged, fragmentation, page cache, swap, memory pressure.** | 56 GiB of THP in production. | All compaction, reclaim and swap counters are 0 since boot. The probe's fresh 64 MiB pinned buffer is slow too. TP expert RAM is not the THP arena at all. Pinned pages do not move. | Diff the `/proc/vmstat` lines in the snapshot across one slow request: all deltas 0. |
| 7 | **Pinned vs pageable source, or a different amount registered per start.** | Main engine's pin amount can depend on free RAM at launch. | Slow state appears and clears inside one process. TP engine pins everything. Probe is pinned and slow. | `grep -n -i -E "cudaHostRegister|page-lock|limited to|FAILED|huge" <local path> Heretic IQ4_XS-32k.engine.log \| head -20`, fast start vs slow start. |
| 8 | **Other host load, IRQ or affinity, NUMA.** | Proxy, quarantine service and monitoring share the host. | One NUMA node. Load average 0.06–1.1. Request audits clean. Does not explain rest curing it. | `top -b -n1` and `/proc/interrupts` deltas in the snapshot. |
| 9 | **NVIDIA persistence mode or P-state transitions.** | Persistence is Disabled. | Only matters with no client; the engine holds a context. Memory clock stays 6800 MHz. | `pstate` column in the 1 Hz sample. |
| 10 | **Strata expert-cache or thread-pool bistability.** | Vision rows went slow inside one old process. | Probe outside the engine is slow. Copied bytes and hit rate identical (82.5% in both). Rest fixes it without restart. Those vision rows came late in a long run, as #1 predicts. | None needed once the probe pair is in; it is already ruled out as the primary cause. |

### What to capture, in both states

| Slow-state result | Meaning |
|---|---|
| memcpy down 30% or more, loop within 5% | #1 memory throttling |
| loop down to about 40%, top MHz about 1200 | #2 CPU clamp |
| neither moves while H2D is slow | host RAM and CPU are fine: look between root port and GPU (#4, #5) |
