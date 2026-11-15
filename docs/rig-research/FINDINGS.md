# Findings and limits

These rankings apply to the November 2026 dual modified-22-GB RTX 2080 Ti rig and Qwen3.8-Flash-Next Heretic IQ4_XS. “Helped” means a useful measured candidate, not a general default change. Advice derived from code is labelled as analysis. Read the [method](METHOD.md) before comparing rates.

## Ranked outcomes

| Rank | Change or finding | Evidence | Decision |
| --- | --- | --- | --- |
| 1 | Measure host state and separate decode from whole-request throughput | Identical early arms differed by about 1.45×; later same-process FAST/SLOW decode differed by about 2.4× | Required for interpreting every speed experiment |
| 2 | Native R2 stage trimming and piped MTP | Early short-prefix matrix C0→C1 lowered TTFT; C1→C2 raised two-stream whole-request throughput 74.8→99.1 tok/s. Final 200k sustained P0/R2 pair: 26.26→30.58, +16.47% | Preferred native baseline; early matrix lacks state-matched sustained repeats |
| 3 | Increase parked-entry count alongside cache bytes | 32 GiB/4 entries lost a busy prefix; 32 GiB/8 kept two busy histories but lost the idle third; final 64 GiB/12 retained every tested continuation | Twelve is tested; indefinite retention and sixteen entries remain open |
| 4 | Use four slots only when four simultaneous histories matter | X4 retained four 128k histories; early 52–54 whole-request tok/s, later 28.7 | More simultaneous users at a lower context ceiling and lower per-stream speed |
| 5 | NVLink peer transport and SM75 recurrence adaptation | 4096-row reductions 1083 versus 6915 µs; 16-column recurrence used 57988 bytes versus the 65536-byte limit | Successful components; no whole-serving TP win follows from them |
| Hurt | TP expert prefetch | A2→A3 warm decode 41.1→24.9 tok/s and host bytes/card 38.001→76.462 GB | Exclude from serving recipe; changing host state and expert capacity confound attribution |
| Failed | R3 concurrent native prefill | Writers kept emitting, then third 128k read produced non-finite logits and cleared cached state | Reject this build/workload despite short-prefix success |
| Incomplete | TP long concurrent qualification | Early ring errors/Xid31; later reuse assertions; final repeated/fairness/sustained trials incomplete | Keep TP out of the tested production recipes |
| No useful saving | Half-and-exchange prefill relay | Layer split reads each expert byte once to its owning card; estimated benefit 0–3% FAST, 0% SLOW | Analysis only; no relay hardware trial |

The early overnight kernel, SIMT and DFlash2 comparisons cannot support a causal ranking because arm order tracked machine state. The short-prefix validation reported prefill-pipe degradation, but its late position also confounded state. Neither result justifies a universal claim that those features are always slower. R2 leaves them off because the selected recipe was tested that way.

## Host-memory throttle evidence

The [truth investigation](reports/strata-tp-truth.md) measured the same loaded process before load, after sustained load and after 600 seconds idle. Means and ranges were from five observations per state.

| Measure | FAST | SLOW | Recovered |
| --- | --- | --- | --- |
| Decode tok/s | 71.260 [67.590,72.684] | 29.557 [28.952,30.223] | 71.552 [67.865,73.085] |
| CPU-only copy GB/s | 9.714 [9.460,9.900] | 3.818 [3.770,3.850] | 9.612 [9.440,9.810] |
| Register/L1 loop Miter/s | 9.214 | 9.462 | 9.188 |
| Fastest active core MHz | 2990 | 2980 | 2988 |
| Package temperature during decode | 44–47°C | 52–53°C | 44–47°C |
| Thermal-counter increments | 0 | 0 | 0 |
| GPU/root-port links | Gen3 x16 | Gen3 x16 | Gen3 x16 |

CPU-only copy fell 60.7% while the compute loop stayed stable. Two concurrent host-to-GPU copies were about 3.84 GB/s per card in SLOW versus 11.82 in the recovered state. GPU-local device-to-device copies stayed about 264 GB/s. This isolates a shared host-memory-path limit more strongly than GPU temperature or engine timing alone. A CPU-only memory workload reproduced the decline with GPUs idle. A whole-CPU 1.2 GHz clamp and PCIe downshift were not observed in these windows.

“Memory throttle” names the observed reversible bandwidth cap. The precise DIMM temperature, controller register, activity limit or board mechanism was not identified. No cooling, firmware, clock, governor or power-limit intervention was measured. Before/after probes in later windows locate endpoints only; they cannot assign every request to FAST or SLOW. In X5, the sustained leg ended SLOW; it was not a controlled isolated SLOW leg.

## TP verdict and copy cost

The [final matched pair](reports/strata-tp-final.md) used two independent ~128k histories and identical paired outputs. Native R2 whole-request throughput was **44.78 tok/s** versus TP **13.69**, a **3.27× observed difference**. Native's first-output waits were 7.38 / 3.77 s versus TP 46.65 / 21.95. Each engine began FAST and ended SLOW, but their trajectories were different and pair states were not separately probed. Native had 8 GiB conversation cache, TP 32 GiB. Native later lost a prefix. This is evidence for choosing the better warm baseline, not a repeated equal-budget, state-controlled engine comparison.

TP sequential reuse worked in window 3: cold 58.0 and warm 87.5 tok/s, 127934 positions reused, FAST at both ends. Its cold 34.08 ms per draft round passed the predeclared 47 ms research cutoff. That kept a narrow research case open; it did not establish superiority over native. The long concurrent cases still lacked the full required acceptance matrix.

The [copy model](reports/strata-tp-slow-review.md) estimated about 3.2 s of non-copy work per 512-output answer plus 42.8 GB/card of host expert copies. Those bytes were stable across host states, giving copy shares near 54% FAST and 83% SLOW. Native R2 often computes an expert miss on the CPU instead of transferring it for GPU compute. Its miss path therefore cannot be inferred from TP's copy cost.

In the final flag matrix, all TP greedy hashes matched the baseline. Copy-engine plus counters improved observed warm decode 34.8→41.1 tok/s over counters alone, but state changed and the cold result worsened. Prefetch then fell to 24.9. It allocated 278528000 bytes/card of staging and displaced 1296 more experts into RAM. Warm transfer bytes doubled and copy waits rose. No prefetch-summary output appeared, so hit rate and wasted bytes were not measured. The proposed destructor/early-exit explanation is unconfirmed static analysis, not a measured profiler result.

The router guard prevents a row with insufficient finite candidates from indexing expert tables unsafely; it reports an error and context. It is not proof that the original non-finite source is fixed. Successful subsequent windows do not erase intermittent earlier failures.

## Cache entries, RAM and stalls

| Test | Live slots / context ceiling | Cache GiB / entry limit | Peak parked GiB | Evictions | Retention outcome |
| --- | --- | --- | --- | --- | --- |
| Final native comparison | 2 / 256k | 8 / historical default 4 | See source report | 18 by round 3 | Prefix misses and >100 s writer gaps |
| X1 | 2 / 256k | 32 / 4 | 10.9 | 12 | Busy history re-read in sustained leg |
| X3 | 2 / 256k | 32 / 8 | 19.5 | 18 | Two busy retained; idle third lost |
| X4 | 4 / 128k | 64 / 12 | 28.38 | 4 | 20/20 continuations hit; all four final checks hit |
| X5 | 2 / 256k | 64 / 12 | 41.75 | 8 | 20/20 hit; idle third checked before sustained churn |

A parked entry is a saved cache state, not a unique conversation or active slot. Restoring a prompt and parking a completed reply can leave multiple generations for one history. Older copies are only sometimes superseded. The observed continuation sequence accumulated roughly two entries per conversation per turn. Twelve parked entries can fill before the 64 GiB budget. X4 ended with about three entries per history; X5's two active histories filled twelve during sustained continuations. Evicted identities were not logged, so “only stale copies were evicted” is an inference.

X4's available RAM fell about 29 GiB to 143 GiB. X5 fell about 42 GiB to 127.9 GiB. These are changes in system available memory, not an independent decomposition of every engine allocation. The configured 64 GiB is a ceiling, not a promise of immediate physical allocation. Keep room for weights, vision, pinned transfers and the operating system. The observed internal minimum-free setting was 2560 MiB; that is not a suitable total rig capacity target.

Cache restoration was 0.26–0.67 s at 128k and 0.40–1.01 s at 200k, much cheaper than ~70–75 s or ~125–130 s cold reads. Cached first-output latency still includes queued restore and suffix prefill. Cold native prompt reads can stop a writer: 73.2 s in X1 and 88.3 s in X3; the final small-cache comparison exceeded 100 s. More bytes and entries reduce the chance of that event, not its cost when it occurs.

R3 allowed writers to continue with largest gaps 1.9 / 1.5 s, but the cold third read failed at position 127936 with non-finite logits and discarded the live session and parked states. Correctness overrides the latency benefit. R3's throughput cost was not isolated because it began SLOW while the preceding R2 test had started FAST.

The [subsequent production application](reports/strata-prod-r2-apply.md) used sixteen entries and verified both modes plus a 32k cached continuation in the two-stream mode. It did not repeat X4/X5's long-context load at sixteen entries. Its rollback script was not exercised. Keep that deployed setting separate from the twelve-entry retention evidence above.

## Relay and remaining work

The [relay scout](reports/strata-prefill-relay.md) was read-only analysis. R2 assigns layers 0–22 to one card and 23–47 to the other. Their expert bytes differ. Relaying half the bytes between cards cannot reduce the bytes read from host RAM, and both PCIe links already run in the prompt pipeline. The proposed relay therefore offered no SLOW-state saving; a few percent FAST was only an analytical upper bound.

Useful unmeasured work includes longer growing-history churn, checking every idle history after sustained eviction, sixteen entries within the same byte budget, full 256k inputs, equal-budget state-matched TP/native repeats and a correctness fix for concurrent prefill. None is represented here as a completed experiment.
