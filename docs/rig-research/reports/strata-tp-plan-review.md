# Strata tp plan review

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

Read-only plan review. Proper TP memory fit requires FNX_ARENA_RESERVE_MIB, not simply increasing the expert-RAM target. The 44 GiB variant left fewer resident experts and cannot stand for a fair TP comparison. Predictions are not hardware validation.

## Retained tables

### 1.3 Live context against cache slots (36 target, 7,034 slots per card)

| Live conversations | Slots lent per card | Share of the cache |
|---|---:|---:|
| up to 44k positions | 0 | 0% |
| one 128k | about 635 | 9% |
| one 200k | about 1,140 | 16% |
| two 128k | about 1,590 | 23% |
| two 200k | about 2,600 | 37% |
| four 200k | about 5,400 | 76%: not usable |

### 1.4 Settings that matter, ranked

| # | Setting | What it does | Use |
|---|---|---|---|
| 1 | `FNX_ARENA_RESERVE_MIB` | Free VRAM at start = this minus about 232 MiB | **640** (predicted 407 MiB free on GPU 0). 768 if the floor must hold with more margin (predicted 535; costs 230 slots per card) |
| 2 | `FNX_EXPERT_RAM_GIB` | Cache slots. Lower is better until the engine has to spill | **36**. Record the actual figure (expect about 38.1 GiB, 16,480 experts, 6,920 slots per card with reserve 640). Not 44 or 48 |
| 3 | `--conversation-cache-mib` | Host RAM for parked conversations. The launcher fixes it at 4096 for TP (`split_engine.py:79`, `:285`), no flag | **32768**, by editing the constant in the task's own copy. Reason below |
| 4 | `--batch` (slots) | 1 = one request at a time, no batched windows. 2 or more = batched windows, the path that failed | 1 and 2 only. 4 is pointless at long context (table 1.3) |
| 5 | `FNX_PEER`, `FNX_PF_PEER` | Window sums and prompt chunk sums over NVLink, not host memory | Both **1**. NVLink does not slow in the slow state (GPU-local copy stayed 264 GB/s), so peer matters more there. Off only as a diagnostic |
| 7 | `FNX_PF_STAGE_ROWS` | Prompt reads shorter than this (default 2048) read RAM experts in place from a kernel; longer reads copy them with the copy engine (`prefill.cu:1295-1296`, `1485-1488`) | Test **0** against the default on a 600-token turn (section 3) |
| 8 | `--spec` | Draft depth, fixed at 6 by the launcher (`split_engine.py:285`). Rejected draft rows still fetch experts | Test 3 against 6 in the slow state only, judged by rounds and bytes per token. Low priority |

### Stage A. Fit and correctness. About 25 minutes, any state, no rests

| Change | If it then passes |
|---|---|
| `FNX_PF_PEER=0` | The fault is the prompt path's peer push beside decode windows |
| `FNX_PEER=0` | The fault is the decode peer push (new CUDA code, `src/split/src/cuda/peer.h`) |
| `FNX_RING_F32=1` | A real fp16 range overflow. Costs about 30% of decode and turns off the one-hop peer path (`engine_common.cu:1012-1019`, `engine.cu:310`) |
| `--parallel 1` | Only the batched-window path fails; TP is then a one-request engine |

### 3. Can TP's copy path be made less sensitive to the throttle?

| # | Change | Kind | Expected | Test |
|---|---|---|---|---|
| 1 | `FNX_ARENA_RESERVE_MIB=640` | Setting | TP starts at the 36 target above the floor | Stage A1 |
| 2 | Conversation cache 32 GiB for TP | One constant in the task's copy of `split_engine.py:79` | No cold re-read after an idle park | Stage A3 |
| 3 | `FNX_PF_STAGE_ROWS=0` | Setting | Short turn reads use the copy engine, overlapped with compute, instead of in-place kernel reads. First token down by up to a quarter in the slow state, by the probe's ratio. Could be worse for very small reads, since a stage copies up to 384 MiB a layer | A 150-token and a 600-token turn at 128k, default against 0, slow state. One start each |
| 5 | `--spec 3` | One constant (`split_engine.py:285`) | Unknown, perhaps ±15% in the slow state | Low priority |
| 6 | Decode miss fill with the copy engine (`kernels.cu:1839-1850` reads host memory from a kernel; the miss list is planned on the card, `moe.cuh:19-40`) | Real code change | Copy time −17 to −27% sustained, by the earlier model | Only after TP passes the kill rule |
| 7 | Read short turn deltas through decode windows, which use the cache | Real code change | First token for a 600-token turn from tens of seconds to a few, estimate | Only if first token is what kills TP and change 3 does not fix it |
