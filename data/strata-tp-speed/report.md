# Split expert-copy and prompt fairness experiments

Local-only implementation, 15 November 2026. Base: local `main`, `457507df`.
Branch: `fm/strata-tp-speed`. No GPU execution, rig access, backend build,
production change, push or publication was performed. **There is no measured
speedup or GPU correctness verdict for these changes yet.**

The assigned advisor report was read from `data/strata-tp-slow-fable/report.md`
in the task's evidence directory. Its bandwidth numbers are prior evidence,
not measurements produced by this worker. The later steering message added
prompt/decode fairness after the window-4 starvation finding. That finding is
also prior evidence; its roughly 1 tok/s result was not reproduced locally.

## Flags

All four switches are OFF when absent or zero. They use the existing strict
integer environment parser. No executable default was changed.

| Switch | Effect when enabled | Limits |
| --- | --- | --- |
| `FNX_CACHE_COPY_ENGINE=1` | Demand expert misses use a host worker and a dedicated nonblocking CUDA copy stream. | Requires an expert cache, mapped pinned host sources, UVA, a copy engine, sm_60+, and a valid clock rate. Unsafe startup configurations fall back to the original SM copy path, with a reason on stderr. HIP uses the original path. |
| `FNX_CACHE_PREFETCH=1` | Guess the next layer's experts with the existing probe router and stage only guessed misses during the current layer's MoE compute. Print a per-card summary at engine destruction. | Requires `FNX_CACHE_COPY_ENGINE=1`. Alone it prints a disabled message. Staging allocation failure disables prefetch and retains demand DMA. |
| `FNX_CACHE_COPY_STATS=1` | Print per-window, per-card host bytes copied and time spent in the copy-wait interval. Works independently with the original SM path. | CUDA timer only. Adds two timing kernels per cached layer and a counter download per window. |
| `FNX_READ_INTERLEAVE=1` | During another lane's prompt read, use smaller prompt slices and run a bounded number of decode windows between slices. | Server path. Only changes reads that begin while another lane is decoding or paused. |

The fairness knobs are read only when `FNX_READ_INTERLEAVE` is enabled:

| Knob | Enabled default | Validation |
| --- | --- | --- |
| `FNX_READ_CHUNK_ROWS` | `2048` | 256 through 8192, a multiple of 256. A chunk cannot exceed the allocated prompt chunk size. |
| `FNX_READ_DECODE_TOKENS` | `8` | Target new tokens for each eligible decoding lane between prompt slices. |
| `FNX_READ_DECODE_WINDOWS` | `8` | Hard window cap per slice. Require `1 <= tokens <= windows <= 256`. |

No flag enables a model approximation, expert skipping, or different weight
quantization. Smaller prompt slices can select different existing prompt GEMM
shapes, so enabled fairness still needs numerical checks on hardware.

## Demand-copy design and eviction safety

The router still makes the real expert choices and CLOCK slot plan on the GPU.
The captured decode graph records two small kernels in place of `k_cache_copy`:

1. A publisher snapshots the miss IDs and their already assigned destination
   addresses into one mapped, pinned mailbox per card. It finishes the payload
   with `__threadfence_system()` before incrementing an aligned 32-bit sequence.
2. A waiter holds the decode stream until the worker publishes the matching
   completion sequence. It uses a system fence before subsequent kernels run.

A dedicated host thread polls each card's mailbox. It resolves the loader's
mapped device aliases to CPU aliases of the pinned source allocations, checks
the request, enqueues gate/up and down with `cudaMemcpyAsync` using
`cudaMemcpyHostToDevice`, and synchronizes **only its private copy stream**.
Only after that synchronization succeeds does it release the completion flag.
No CUDA API is called from a CUDA host callback. Capture itself creates no
mailbox request; the kernels publish fresh requests on every graph replay.

There is one outstanding request per card. The next publication waits for the
previous completion before changing the payload. The decode stream cannot
reach an MoE reader or a later CLOCK plan before demand DMA has finished.
Other engine operations, including arena changes and prompt passes, execute
between completed windows. Thus destinations cannot be evicted while the host
worker is writing them. The shared-expert stream does not plan cache slots.
Before publication the GPU also checks expert range, pool bounds, lent-slot
bounds and the slot's owner. The host validates the destination range/alignment.
Graph destruction precedes worker shutdown; workers stop before engine-owned
buffers are released.

The handshake uses naturally aligned 32-bit loads/stores, not host/device
read-modify-write atomics. Host accesses use compiler acquire/release atomics;
GPU accesses to sequence, completion and status are volatile. This relies on
CUDA's coherent mapped host-memory and system-fence ordering. **The CPU mock
does not verify those device/PCIe ordering assumptions.** Validate them on the
target driver, GPU and topology before enabling this outside an experiment.

Fallback is decided before capture: unsupported properties, source layouts,
alias lookup, or mailbox/stream setup failure retain the original SM kernel.
Once a DMA request has been published, an error cannot safely switch to an SM
writer while DMA might still be running. Copy errors therefore publish failure
and trap the graph; the waiter also traps on a bounded clock-based timeout
(nominally 30 seconds at the reported GPU clock). It never releases a reader
to a partly filled slot. Clock throttling can lengthen that timeout; use an
external test timeout as well.

## Prefetch design and counters

The guess is exactly the existing `FNX_PREFETCH_PROBE` computation: apply layer
`l+1`'s router to layer `l`'s normalized FFN input, then take its top ten per row.
The additional router runs on each card that has prefetch enabled. The existing
probe-only scoring behavior is retained when separately requested.

After layer `l`'s demand fill, the graph publishes the distinct guessed experts
of `l+1` that currently have no slot. Duplicates, resident experts, and invalid
probe sentinels are excluded. The copy stream puts these matrices in **private
staging**, never into CLOCK slots, while layer `l`'s MoE and subsequent work run.
The next demand submission waits for staging to finish, then copies actually
needed staged experts D2D into the real planner's slots. Unpredicted demand
misses use H2D as before. It then discards the remaining staged guesses.

Staging costs `160 * max_layer(gate_up_stride + down_stride)` bytes per card.
It is allocated before the K/V arena is sized, so it is accounted for in free
VRAM, but it can reduce the K/V pages available. Failure to allocate it leaves
the demand copy engine usable. The first layer has no prediction; the last
layer starts none. A complete window consumes every prediction it creates.

The engine destructor prints `expert prefetch summary` on stderr for each
enabled card: miss guesses, used guesses, guess hit rate, bytes prefetched and
bytes wasted. **Hit rate means useful staged miss guesses / all staged miss
guesses**, not coverage of all routing picks. Wasted bytes are staged matrices
that the next real miss list did not use. An interrupted window's outstanding
staging is also counted as wasted at shutdown. Totals include warmup windows.

This design preserves the real CLOCK decisions. With identical routing/cache
state, total H2D bytes with prefetch should equal baseline demand bytes plus
wasted prefetch bytes. Useful predictions move transfer earlier; they do not
reduce total host traffic. They also add D2D traffic. A bad guess rate, a short
overlap interval, or bus contention can make prefetch slower.

With `FNX_CACHE_COPY_STATS=1`, each completed `window`, `step`, or `verify_rows`
prints its row count, cached layer count, host bytes copied and `copy wait` in
milliseconds. SM bytes are miss count times the layer's two matrix sizes. DMA
bytes come from successfully completed H2D transfers, including wasted prefetch
and excluding staging D2D. Counters are cumulative internally and printed as
window deltas. There are no prompt-copy or embedding bytes in this metric.

The timer uses CUDA `%globaltimer` nanoseconds. It starts after the real slot
plan and ends after the demand fill barrier. It includes handoff, scheduling,
empty-list round trips, demand DMA and any remaining wait for prior prefetch;
it excludes prefetch time already overlapped with compute. It is a critical
copy interval, not a profiler measurement of DMA duration. Compare both arms
with counters enabled, then time again with counters disabled. Do not sum
per-card wait times as if they were sequential wall time.

## Prompt/decode fairness

The old server already ran one decode window at each prompt progress callback
and capped a prompt pass at 8192 rows while other lanes decoded. The new flag
reduces actual prompt chunk sizes as well as the pass limit; reducing only the
pass limit cannot split an already allocated 8192-row chunk.

At each progress boundary the server snapshots token counts for decoding and
paused lanes, then runs existing `decode_step()` windows until every surviving
eligible lane reaches the token target or the window cap is exhausted. A
greedy lane that advances every window therefore reaches eight tokens with
the default budget; speculative acceptance may reach the target sooner. EOS,
length completion and cancellation remove a lane's target. Page-starved or
paused lanes can miss the target; the hard cap still bounds the work, and the
stderr progress record says `targets met no`. Reader STOP/BSTOP/BYIELD is
checked between decode windows as well as before the yield.

The existing lane switching, batch decoder and session/checkpoint logic are
used unchanged. Each prompt pass finishes before decoding starts, and each
decode window finishes before prompt work resumes. The default chunk size,
one-window progress behavior, and admission policy remain when the flag is off.
The new knobs do not alter `FNX_ADMIT_INTERLEAVE`.

Stderr records prompt progress, decode windows used, total emitted tokens,
whether targets were met, and time spent decoding at the yield. More decode
work and smaller prompt GEMMs add cold-read time. Host preparation of the
following slice is still done within the existing prefill pipeline; there is
no promise of a strict wall-clock latency bound per slice.

## Local validation

Passed on the disposable Linux CPU worktree, code revision `774b3d33`:

- `python3 -m pytest tests/split -q`: **79 passed in 15.97s**. The initial
  copy-only stage also passed all 78 tests then present.
- New C++ tests, compiled by pytest with `g++ -std=c++17 -O2 -pthread -Wall
  -Wextra -Werror` for the host worker and without `-pthread` for the scheduler.
  The actual host worker uses a fake CUDA runtime: pinned-layout fallback,
  repeated destination reuse, unsigned sequence equality at wrap, both matrix
  copies, invalid destinations, copy errors, missing-guess selection,
  speculative D2D reuse, empty lists, host byte totals, and summary accounting.
  The scheduler tests disabled-knob handling, invalid limits, chunk bounds,
  unequal per-lane progress, speculative completion, inactive lanes, and a
  stalled lane's hard budget cap.
- The host worker test compiled with `-O1 -g -fsanitize=address,undefined
  -fno-omit-frame-pointer` and ran successfully with the fake runtime. Its log's
  deliberate fake-copy and invalid-destination errors are expected assertions,
  not sanitizer failures.
- CPU syntax check of `src/split/tools/sfnx.cpp` using `g++ -std=c++17
  -fsyntax-only -D__host__= -D__device__= -DFNX_NCARD=2 -DFNX_27B=0 -DFNX_HIP=0
  -DFNX_HOSTRING=1` and the test fake CUDA include directory.
- Static source comparison against `457507df`: `moe.cuh`, `router_topk.cuh`,
  `session.cpp`, and `batch.cpp` are unchanged. The original `k_cache_copy`
  kernel body and `router_route` launcher are unchanged. All new allocations,
  launches and logging require their respective switches. The zero-slice
  helper returns the original allocated chunk size.
- `git diff --check` passed.

The sanitizer and server syntax checks ran at `f6c6e9a0`; the only later source
change adds checks inside the CUDA publisher and does not change those CPU
paths. The full split suite was rerun at `774b3d33` after those checks were added.

Corrected local harness attempts: `python` was unavailable, so tests used
`python3`. The first fake-runtime syntax check lacked the CUDA annotation
macros; the corrected command above passed. No unresolved local check failed.
Proof logs and temporary binaries are outside the repository in the task's
evidence directory.

Not run: nvcc, HIP or SYCL builds; GPU execution; the 4k greedy hash; actual
captured graph replay and mapped-memory ordering; hardware router-guard cases;
DMA/compute overlap profiling; warm/shared-prefix checks; 128k concurrent-lane
tests; speed or bandwidth benchmarks. SYCL is not an enabled split backend.
Static equivalence is not a claim that the 4k hash passed on hardware.

## Required rig checks before a verdict

1. **Build and identify.** Firstmate builds the CUDA split binary for sm_75 on
   the 2080 Ti pair, its tests, and the HIP split fallback configuration because
   shared files changed. Record head, toolchain, binary SHA256, model hashes,
   memory settings, environment and actual argv. A fake-runtime CPU check is
   not a backend build. Preserve the finite-row router-guard GPU test results.
2. **Prove flags-off compatibility first.** Compare this head with same-day
   `457507df`, same model, same settings and same prompts. Run the existing 4k
   greedy token/hash fixture with all four switches absent, then explicitly
   zero. Require identical token IDs/hash and no new flag messages. Exercise
   invalid router rows and retain the existing lane/layer/row diagnostics.
3. **Correctness matrix.** Test counters only; demand DMA only; demand DMA plus
   counters; DMA plus prefetch; all three; and prefetch requested without DMA.
   Run T=1 through 16, repeated graph replay, alternating graph shapes/lane
   layouts, MTP off/on, greedy/speculative decoding, empty miss lists, cold and
   warm cache, and mixed expert matrix sizes. Use compute-sanitizer where
   supported. Check all outputs against the same-head SM arm, with the same
   routing and no expert skipping. Require the 4k hash in every copy arm.
4. **Stress eviction and ownership.** Use the actual 36-GiB host-expert setting,
   small cache capacity, repeated eviction, the 128k arena lending slots and
   giving them back, two lanes, sequential prefix reuse, and concurrent
   shared-prefix requests. Test engine destruction/recreation and request
   cancellation. The worker must never write a slot after its reader or a
   later planner starts. Include delayed/failed-copy fault injection in an
   isolated test harness: errors must terminate, never expose partial data.
5. **Prove the mechanism.** Capture a timeline showing actual copy-engine H2D
   on the private stream, demand completion before MoE, and staging copies
   overlapping the prior layer's MoE. Check for capture-time requests, graph
   replay deadlocks, slot corruption, CPU polling cost, and additional VRAM
   pressure. Bound every test externally. GPU sanitizer alone cannot prove
   the CPU/device mapped-memory handshake.
6. **Check the numbers.** A full cached decode window should report 48 layers
   per card. With prefetch off, DMA and SM host byte totals should match for
   identical routes/cache state. With prefetch on, verify `prefetched = useful
   + wasted` bytes after complete windows and the baseline-plus-waste H2D
   relationship above. Empty lists must not invent host bytes. Compare the
   two cards separately and sum bytes only when reporting aggregate traffic.
7. **Measure demand DMA separately from prefetch.** Use matched short-code and
   cold/warm 128k fixtures, one request at a time first. Record host-memory
   probes before and after each arm, and label FAST/SLOW/transitional states.
   Collect repeated warmed runs of baseline, DMA, and DMA+prefetch with the
   same counters, then without counters. Record individual wall times, tok/s,
   rounds, accepted drafts, ms/round, wait ms, bytes, hit rate and waste. Keep
   failures and variability. A copy-engine bandwidth improvement alone is
   not an end-to-end speedup. Do not compare different host states.
8. **Test fairness independently.** With copy switches off, start a long enough
   greedy decoding request in one lane, then admit a distinct cold 128k prompt
   in another. Measure the first lane's tokens emitted **during the read**,
   tok/s over that exact interval, maximum token gap, and the cold read's
   elapsed time and time to first token. Compare flag-off with defaults
   `(2048,8,8)`, then `(4096,8,8)` and `(2048,16,16)` for the three knobs.
   Ensure the first request lasts for the full read and has page headroom.
   Check progress logs for real slice sizes, budget caps and unmet targets.
   Report added cold-read time as a delta and percentage against the matched
   off arm. Repeat with MTP and the full copy/prefetch combination after the
   isolated fairness check. Verify EOS, STOP/BSTOP/BYIELD during the budget,
   page shortage, warm continuation reuse, and the reading lane's output
   against a fresh isolated read. Repeat the window-4 concurrent prefix case;
   stop and retain diagnostics on the first correctness failure.

Keep all switches opt-in until those results exist. Firstmate owns the later
builds, guarded rig window, acceptance decision and local merge.
