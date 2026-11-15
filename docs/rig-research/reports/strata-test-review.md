# Strata test review

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

Independent review of the early test matrix. It documents arm-order and host-state confounding, insufficient TP repeats and limits of short-prefix concurrency claims. Advice tables are proposals; CPU-copy state evidence derives from the later truth measurements.

## Retained tables

### 1.1 New evidence from the raw files

| Arm | Start UTC | 2 streams, cycles 1/2/3 | 4 streams, cycles 1/2/3 | 4 streams, wall s |
|---|---|---|---|---|
| C0 | 07:54:28 | 72.0 / 73.2 / 73.2 | 105.7 / 108.6 / 107.5 | 22.6 / 22.4 / 22.7 |
| C1 | 07:58:39 | 75.4 / 74.8 / 74.2 | 110.2 / 109.9 / 111.2 | 20.8 / 20.9 / 20.9 |
| C2 | 08:05:26 | 102.1 / 98.2 / 97.0 | 131.1 / 129.0 / 126.9 | 18.5 / 19.0 / 19.6 |
| C3 | 08:09:01 | 100.5 / 98.7 / 97.2 | 130.0 / 127.4 / 125.5 | 18.7 / 19.0 / 19.3 |
| C4 | 08:12:36 | 101.4 / 99.4 / **93.8** | 132.1 / 129.5 / **109.4** | 18.5 / 18.8 / **24.1** |
| C5 | 08:16:49 | 102.1 / **79.0 / 79.6** | **88.8 / 102.7 / 103.7** | **26.3 / 27.2 / 26.5** |
| TP | 08:22:38 | **37.3** (one run) | not run | |

### 1.1 New evidence from the raw files

| Workload | Layer split 0.1.59 (patch 1), decode tok/s | TP, peer off, 36 GiB, decode tok/s | First token, layer split / TP |
|---|---|---|---|
| Code | 21.8–33.5 | 28.4–29.3 | 2.2–2.9 s / 17.1–17.3 s |
| 4k text | 30.8–41.2 | 28.4–35.0 | 6.3–7.3 s / 13.3–13.5 s |
| 32k continuation | 25.4–31.5 | 29.7–30.9 | 2.1–3.8 s (one cold 29.8) / 13.9–30.9 s |
| 1 image | 29.5–32.9 | 21.8–33.9 | 2.4–3.5 s / 18.4–19.4 s |

### 1.1 New evidence from the raw files

| State | One thread, memcpy GB/s | Four threads at once, each / summed | CPU loop, Miter/s |
|---|---|---|---|
| Fast (start) | 9.5–9.9 | about 4.0–5.1 / about 16–20 | 8.6–9.6 |
| Slow | 3.77–3.85 | 0.91–1.39 / about 3.7–4.4 | 8.8–9.7 |
| After 600 s idle | 9.4–9.8 | about 3.7–5.6 / about 15–20 | 8.8–9.8 |

### 1.2 Flaws, ranked

| # | Flaw | What it puts in doubt | Evidence |
|---|---|---|---|
| 1 | **Arm order equals machine state.** Arms run one after another with no rest and no state check. | C5 "harmful", C4 "unstable", TP 34.3 / 37.3, "layer split 2.65× better". Overnight: A1 fast, A2–A8 and the production re-baseline slow, so the ranking table, "SM75 kernels −33%", "SIMT −27%", "DFlash2 −26%" and "0.1.59 (patch 1) is far faster than production". | Table 1.1; earlier review report section 0 |
| 2 | **Stage order inside an arm equals state.** The overnight battery always ran code first and 128k, vision and concurrency last. Early stages were fast, late stages slow. | Any comparison of workloads inside one arm (for example "4k text decodes at 16–28 but code at 39–76"). A4: code 75.5, then 4k text 27.9. | `rig-night-run/report.md` decode table |
| 3 | **Fast-state-only gains.** Each C arm put about 2 minutes of load on the rig, under the onset time. | 99 and 129 tok/s, C1's −22% first token and +25–30% prefill, C2's gain. None has a slow-state value. Layer split loses 2.5× or more in the slow state at one stream (1.1). | C0–C5 timestamps; `tp-truth-v2` |
| 4 | **Diag-0 never reached the slow state.** Three back-to-back runs were about 75–100 s of load; prefill stayed 1,614–1,689 tok/s. | "Thermal and heat soak refuted". It tested the wrong thing: GPU clocks, not host memory, and not for long enough. | `rig-validate-run/report.md` section 2 |
| 5 | **Overlap window shrinks when streams start apart.** Aggregate counts only tokens between the last first-token and the first last-token. With C3 the window fell from about 14 s and 1,812 tokens to 10.3 s and 1,337 tokens, so per-stream rates include time when fewer streams ran. | C3 "+11.3% per stream". Wall time did not improve. C3's real job (running streams do not stall while a long prompt is read) was never tested: the prompt was about 100 tokens. | `decode_bench.py:253-270`; table 1.1 |
| 7 | **Short prompts stand in for long-context use.** The recipe was measured on a 100-token code-like prompt. | Draft acceptance, expert hit rate and KV traffic all change with content and length: layer-split hit rate 77% on first short requests and 98.8% on a 129.6k prompt (production engine log lines 109 and 859); TP hit rate 74.5% on 32k continuations, 82.5% on code, 90% on 4k text (`tp-truth-cpu/window.log`). | logs named |
| 9 | **Single runs.** TP in the validation run: one run per cell. The transport probe: one block per state. | TP verdicts; the exact slow-state transfer rates. | `TP.json`; `tp-truth/report.md` |
| 10 | **Expert cache and prompt path share slots.** In layer split the prompt path borrows 2,022 and 1,966 cache slots (4.57 GiB per card). Decode right after a long read starts from a different cache than steady decode. | Decode speed measured straight after a long prompt against decode after a short one. Not measured apart. | production engine log lines 52–53 |
| 11 | **The report text and its data disagree on outside requests.** The text says 0. The files say `unprompted_rogue_requests` 6 (C0–C2) and 12 (C3–C5), 27 or 33 prompts received for 21 sent. Likely the benchmark's own warm-ups, but nobody checked. | The "no other traffic" claim for the C arms. | `results/C*.json`, field `engine_prompts` |
| 12 | **Vision was "on" but mostly not exercised.** Images go through a CPU reader (16 threads, no VRAM). It competes for the same throttled memory bus. Only one stream with images has been timed. | Vision under 2–4 streams in the slow state: unknown. | `rig-night-run/report.md` header; earlier review report answer 3 |
| 13 | **VRAM margin measured on short prompts.** C2–C5 ended with 320–338 MiB free on CUDA1 at 128k and 4 slots. The engine itself calls 413 MiB "LOW" and asks for `--vram-reserve-later-mib 1055`. | Whether 256k with 4 slots is safe. The on-hold brief's floor is 300 MiB. | `results/C*.json` `gpu_final`; production engine log line 66 |

### 2. What is missing that could raise speed

| Rank | Idea | Expected gain | Effort | Risk | Mark |
|---|---|---|---|---|---|
| 3 | **Keep long conversations reusable.** Size the conversation cache for 4 slots of up to 200k (`conversation-cache-gib`; overnight arm A8: 32 GiB, 99.8% hit, 0 evictions at 2 slots and 32k). A cold 200k read is about 190 s at production's 1,037 tok/s and by itself brings on the slow state. | Minutes per turn where a turn would otherwise be re-read | Low | RAM: check it against the 36 GiB TP arena if TP is used | **Test now** |
| 6 | **Draft depth for the sustained state.** When copies dominate, a window's extra draft rows cost little if they route to the same experts, so the best depth is probably deeper than in the fast state. Sweep `spec` 3, 6, 8 on TP (it ran 6) and 3, 4, 6 on layer split (it runs 3), judged by bytes copied per accepted token. | Unknown, perhaps ±15% | Low | Deeper drafts lower acceptance on prose | **Test now** |
| 7 | **How much do streams share experts?** Measure bytes copied (TP) or misses (layer split) per generated token at 1, 2 and 4 streams. If they share little, 4 streams in the sustained state give no more total speed than 2, only longer first tokens. | Decides "4 if possible, else 2" | Low, counters only | None | **Test now** |
| 9 | **Overlap copies with compute** (`STRATA_KV_PREFETCH` for long-context prompt reads, `docs/KV_PREFETCH.md`; `STRATA_DMA_BATCH=1` or `2`, `docs/BATCHED_DMA.md`, experimental). | Fast state only: when the bus is the cap, overlap does not raise it | Low | Experimental switches | Test now, low priority |
| 10 | **`--pcie-frac` in the sustained state** (0, 0.33 as now, 0.55): CPU compute against GPU copy for misses. Both read the same bytes from the same throttled memory. | Small | Low | None | Test now, low priority |
| 11 | **Fetch experts from the other card over NVLink.** There is no VRAM to hold second copies. In TP each card holds its own half of every expert. TP leaves about 1.5 GiB free on GPU 1 only (`TP.json`: 284 and 1,484 MiB free), room for about 2% of the experts. | About 0 | High | | **Skip** |
| 12 | **Expert-parallel placement, routing locality.** What fits is set by 44 GB of VRAM minus dense weights and KV, whichever layout. Trim (C1) already removes the duplicate dense weights. | About 0 beyond C1 | High | | **Skip** |
| 13 | **Hugepages for TP's mapped buffers.** Pinned pages do not move, the probe's fresh 64 MiB pinned buffer is slow too, and all compaction and swap counters are 0. | 0 | | Takes RAM for good | **Skip** |
| 14 | **NUMA, CPU governor, C-states, PCIe link.** One socket. Measured unchanged in the slow state: cores near 3 GHz, CPU loop 9.2 → 9.5, Gen3 x16. | 0 | | | **Skip** |
| 15 | **Memory speed and population.** All 4 channels are full (8 × 32 GB registered DDR3, 2 per channel). Cooler or fewer DIMMs (low-voltage parts, or one per channel) only make sense after item 1 says heat is the cause. | Unknown | High: new parts | 128 GB would not hold the model, the TP arena and the caches | Needs hardware, later |

### 3. Ordered plan

| Result | Meaning | Next |
|---|---|---|
| (c) never trips | There is a sustainable traffic level near half. Pacing or fewer streams can stay fast. | Step 2 measures which recipe stays under it |
