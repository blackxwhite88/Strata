# Strata tp fix review

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

Read-only review of the guard/diagnostic plan. It corrects an earlier source-identity claim: the CUDA peer port was already committed at 6dd2cdd9. Root-cause candidates based on code are unconfirmed static analysis.

## Retained tables

### 2. What the logs add about the three failures

| Run | Other lane reading? | Slots lent at failure | Where the bad value showed |
|---|---|---|---|
| Wave 2 (RAM 44) | no | 0 (own pool 1,269 pages, no growth line) | first batched window of a lane at 128,553, right after the lane changed slot |
| Wave 5b primary | yes, cold 128k | 578 | inside a read pass (`prefill: ring error 2`) |
| Wave 5b PF_HOST | yes, cold 128k | 662 | inside the writer's decode window, a lane about 1-2k tokens long |

### 4. The diagnostic window (under 25 minutes)

| Arm 1: `FNX_PEER=0 FNX_PF_PEER=0` | Arm 2 | What arm 2 tells |
|---|---|---|
| fails | peer off, `FNX_EXPERT_RAM_GIB=44` (own pool 1,269 pages as in wave 2, so nothing is lent; check there is no `arena: K/V pool` growth line) | passes: lending (H1). fails: the two-lane path at long length, lending not needed (H3) |
| passes | peer on, prompt peer on (the wave 5b primary) | fails: the CUDA peer push (H2), shown on one binary. passes: the short script does not reproduce; arm 3 repeats arm 2 with the 64k step first |

### 4. The diagnostic window (under 25 minutes)

| Branch | Arm 3 | Arm 4 |
|---|---|---|
| H1, lending | peer off, RAM 36, `FNX_ARENA_BASE_PAGES=100`, `FNX_ARENA_CHURN=1`, S2 with the 32k fixture. A fail gives a two-minute reproducer for `compute-sanitizer` later | if arm 3 passed: the same with a 96k read |
| H3, long two-lane path | peer off, RAM 44, `FNX_CAPTURE_AFTER=1000000` (windows run without a held graph). passes: stale graph state. fails: kernel or lane state | none |
| H2, peer | `FNX_PEER=1 FNX_PEER_PARTS=1 FNX_PF_PEER=0` (window sums only) | `FNX_PEER_PARTS=2` (attention merge only) |

### 4. The diagnostic window (under 25 minutes)

| Step | Minutes |
|---|---:|
| Stop production, checks, C6 kernel test | 1.5 |
| An arm that passes: load 1.0 + S1 0.2 + S2 about 2.3 + S3 0.5 | 4.0 |
| An arm that fails (the failures came at 98k to 123k of the read) | 3.0 |
| Four arms, worst case | 16.0 |
| Restore and verify | 2.5 |
| **Total, worst case** | **20.0** |

### 5. What "TP is fixed" should mean

| Context | Cases, all in one process | Repeats |
|---|---|---|
| 64k | cold read beside a 2,048-token writer (2,048 + 512 tokens, marker recalled); a reused turn; two requests on the same prefix | 3 |
| 128k | the same three; the wave 2 shape (rewind, 618 read, batched window past 128.5k); a lane parked after 120 s idle and resumed; then a 30-minute soak of cold reads and writers in turn, so that lend, give back and lend again all run | 3, soak once |
| 200k | context 208k, labelled "untested-context override" until this passes: a cold 200k read alone and beside a writer; a reused 200k turn with two active; more than 1,000 slots lent at some point | 2 |

### 6. Odds, and what would make TP worth continuing

| Question | My odds |
|---|---:|
| The window names the cause (or shows there are two) | about 70% |
| TP passes section 5 at 128k within one or two more windows | about 50% |
| A correct TP beats R2 on rested single-stream decode at 64k to 128k | about 25% |
| A correct TP beats R2 on sustained long-context turns (the real use) | about 10% |
| A correct TP beats R2 on cold reads | under 5% |
| **TP becomes the long-context recipe on this rig** | **about 10%** |
