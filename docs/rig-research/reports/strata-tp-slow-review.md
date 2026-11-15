# Strata tp slow review

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

Read-only analysis of saved observations. A two-part transfer model estimated expert copy cost at 54% of FAST decode time and 83% of SLOW time. Estimates and proposed improvements in these tables are hypotheses, not new measured speedups.

## Retained tables

### The numbers (saved logs)

| State | Decode tok/s | Time for 512 tokens | Expert copies per answer | Hit rate |
|---|---:|---:|---:|---:|
| Fast | 71.2 | 7.19 s | 85.6 GB (42.8 GB per card) | 82.1% |
| Slow | 28.4 | 18.05 s | 85.6 GB | 82.1% |
| Recovered after 600 s idle | 71.4 | 7.17 s | 85.6 GB | 82.1% |

### The numbers (saved logs)

| State | Copy time (model) | Rest of decode | Copy share |
|---|---:|---:|---:|
| Fast | 42.8 / 11.05 = 3.87 s | 7.19 − 3.87 = **3.32 s** | 54% |
| Slow | 42.8 / 2.87 = 14.9 s | 18.05 − 14.9 = **3.15 s** | 83% |

### The numbers (saved logs)

| Cost | Share of TP decode | Evidence |
|---|---|---|
| Expert paging from host RAM (the copy) | **54% fast, 83% slow** | above; copies and hit rate unchanged across states |
| Host-memory throttle | Turns 3.9 s of copies into 14.9 s: the whole 2.5x swing | CPU-only memcpy falls 9.7 → 3.8 GB/s with GPUs idle (`report.md:23-24`) |
| Compute, attention, ring sums, launches | the remaining ~3.2 s (46% fast, 17% slow) | same in both states |
| Peer reduction alone | small, estimated under 5% of a round | flag round trip ≤ 1.9 µs (`window2 A-peer-on.engine.log:16`); 2 sums × 48 layers a round |
| Launch overhead | small | the decode window is one captured graph (`engine.cu:980`) |

### At 128k (the window logs)

| Run | Tokens | Time | Draft rounds | ms per round | Tokens per round |
|---|---:|---:|---:|---:|---:|
| TP, short context, one lane (`:56`) | 1,147 | 22.5 s | 282 | **79.8** | 4.07 |
| TP, 128k lane beside a short writer (`:51-53`) | 512 | 25.9 s | 306 | **84.7** | 1.67 |
| TP, 128k lane, nearly alone (`:73-75`) | 64 | 3.6 s | 37 | **96.6** | 1.73 |
| R2, cold 128k, same `128k.json` fixture (`recipe-pilot0/R2-128k.warm-startup.txt`) | 512 | 8.84 s | 281 | **31.5** | 1.82 |
| R2, warm 128k continuation (`recipe-wave2` logs) | 512 | 5.1–5.8 s | 104–116 | 46–50 | 4.4–4.9 |

### 3. Improvements that keep the model's quantization, ranked

| # | Change | Expected gain | Effort | Risk |
|---|---|---|---|---|
| 3 | **Fill misses with the copy engine instead of SM threads reading mapped memory** (`kernels.cu:1839-1863`) | Slow: 18.05 → 14.3 s, **+26%**. Fast: +5%. From the measured 3.84 against 2.87 GB/s | Medium–high: the miss list is planned on the GPU, so it needs a host thread watching a mapped list, or a graph rework; 1–2 weeks | Medium: races with slot eviction inside the captured graph |
| 4 | **Prefetch the next layer's misses during this layer's compute** (the guess already exists in `FNX_PREFETCH_PROBE`) | Bounded by the overlap: fast up to 7.19 → ~3.9 s (1.8x) only if guesses are near perfect; slow at most 1.2x, and wrong guesses add bytes when the bus is the limit | High: 2+ weeks | Medium. Measure the guess rate first (`fnx_run`, about 2 minutes) |
| 5 | **CPU computes misses** (port R2's CPU expert workers into the split engine) | Fast: perhaps 1.5x by removing the copy from the critical path. Slow: perhaps +30–40%, since a CPU read moves the bytes once and the DRAM cap is shared anyway | High: 3–4 weeks. It rebuilds what the layer split already has | Medium–high |
| 6 | **Keep K/V out of the expert cache at long context** (K/V streaming like native `--kv-resident`; or 1 slot instead of 2 for a single user) | At 128k: about 1,606 slots per card back, perhaps 10–15% fewer copies. One slot is a setting with perhaps 5–10% | Setting: trivial. Streaming: high | Low (setting) / medium |
| 7 | **Shallower drafts at long context** (`--spec 6` → 3 or 4, `strata_control/split_engine.py:278`) | ±10–15%, content dependent: acceptance at 128k was only 0.42–0.58 | Trivial | Low |
| 8 | Expert-parallel placement instead of slicing | About 0: same bytes (TP does not replicate experts) plus load imbalance and all-to-all | High | Medium. **Do not do.** |
| 9 | Pinned memory, hugepages | About 0: experts are already pinned and mapped; THP is `madvise` with 56 GB in anonymous huge pages (rig, read-only) | Low | Low. **Skip** (plan-review agrees) |
| 10 | Graph capture, launch tuning, faster peer sums | Under 5%: already captured, peer push already on | Medium | Low. **Skip** |
