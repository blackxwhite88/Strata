# Benchmark method

The programme evolved as early measurement flaws were found. Historical tables preserve what was reported, including failed and censored cells. The protocol below describes the later interpretation rules and a reproducible follow-up method. It does not imply that every earlier arm met them.

## Pin identity and isolate each candidate

Record source commit, actual executable digest, toolchain/runtime, GPU model and usable capacity, CPU, RAM population/speed, links, context, active slots, draft settings and cache bytes/entries. Verify the running process argv and selected engine environment, not just the intended launcher command. Check live engine/metrics values for slots and cache limits. Isolate saved launch state, profiles and runtime files; inherited settings can silently alter drafting or select another binary. Keep the model quantization and CPU vision reader fixed.

Use a same-session baseline before and after a candidate. Match both engine cache budgets and host state for a causal comparison. The final historical TP/native pair did not meet the equal-cache-budget condition and is reported with that limit. Do not compare a short-prefix matrix with a 128k cached-pair leg as if they were the same workload.

## Requests and correctness

Use only newly generated synthetic material. The original prompts, images and fixtures are excluded. Give independent histories a distinct nonce near the first user content so that they do not share a long prefix. Hold each base history fixed across its continuation rounds; change the suffix nonce for each measured turn. Record the numeric seed (the final drivers used 40261114), nonce identifier, input digest and request settings without retaining request text in a public result.

Set temperature to zero, thinking off and a fixed seed. Temperature zero alone does not prove cross-engine numerical identity. Generate at least **512 output positions per timed performance request**, check the returned usage count and require the expected synthetic markers. The historical windows also used shorter diagnostic cases: 64-position trigger checks, 128-position loss checks and 256-position rotations. These are not 512-position throughput qualification. The third-read fairness writers requested 2048 outputs to remain active while the new prompt was admitted.

Warm up the chosen shape, discard warmups and prime each independent history separately. Then run three paired or four-way continuation groups, a loss check of every history and a sustained leg. Log whether requests actually overlap and whether each continuation reports a sufficiently large reused prefix (`cache_n`). A “warm pair” with one zero-reuse request fails the warm protocol even if both return plausible text. Exact output hashes compare only the same input and history. New synthetic histories will have new hashes.

For a third-cold-read test, start long writers, establish emission, then admit a separately nonced cold history. Distinguish time queued for an active slot from time spent reading the prompt. Report the longest pause of every writer and the new request's first-output time. If deriving the read interval from server timing rather than a profiler, label that interval as an estimate.

## Rates and clocks

Use monotonic client clocks for send, first content, last content, finish and every streamed fragment. SSE chunks need not correspond one-to-one with model positions. Join reasoning/content consistently with the measured protocol. Retain only numeric event times, lengths and hashes in shareable results; text and prompts stay out.

| Metric | Definition |
| --- | --- |
| First-output latency (TTFT) | First nonempty streamed content time minus request send time |
| Emission-window decode | `(completion count - 1) / (last content time - first content time)`; a chunk-level approximation |
| Engine decode | Engine `predicted_per_second`, labelled separately from client timing |
| Whole-request group throughput | Sum of completed usage counts divided by last finish minus earliest send |
| Per-stream decode sum | Sum of emission-window rates; not whole-request throughput |
| Largest service gap | Maximum time between adjacent content-bearing SSE fragments |
| Prefill throughput | Newly read positions / engine prompt-read seconds; label cold versus suffix |
| Reuse | Engine `cache_n`, accompanied by fresh `prompt_n` |

Do not average pair throughput rates when durations differ. Divide total work by total elapsed time for a combined rate. Report individual runs, means/ranges and independent rest-block counts. A repeated request within one window is not an independent recovered-state repeat. Failed, skipped and time-censored legs remain in the report and are excluded from success claims.

## FAST and SLOW gates

Run the same CPU-memory copy probe three times before and after each arm. Later windows used FAST ≥9 GB/s and SLOW ≤4.5 GB/s. Intermediate samples or a mixed set are neither a pure FAST nor a pure SLOW arm. Some historical driver helpers labelled everything below 9 as SLOW; use the actual numeric samples and these three-way rules when reducing them.

The original copy-probe implementation is not present among the specified window source exports. Archived window drivers retain its invocation and parser, not that missing implementation. Substituting a different buffer size, threading pattern or copy loop changes the calibration. Calibrate any replacement against known recovered and loaded states; do not assume its absolute GB/s values qualify under the historical thresholds.

For a state investigation, keep the same engine loaded through sustained requests and 600 seconds idle. Compare CPU-only copy, register/L1 loop, host-to-device per-card and dual-card transfers, GPU-local copies, clocks, links, temperature and thermal counters. A reversible copy slowdown with a stable compute loop supports a memory-path limit; it does not identify a DIMM sensor or controller register. Probing only window endpoints cannot identify the exact transition time or a request's state.

## Guards and safety floors

Use an exclusive idle maintenance window. Save the existing service's launcher and component/profile identities. Arm a detached rig-local guard **before** stopping that service; verify it can restore the saved launcher exactly once even if the request driver exits. The guard owns the hard deadline and restoration, with process ownership checks so it cannot stop unrelated services. The portable request driver supplied here does not implement service lifecycle or that guard.

Historical post-fix TP windows stopped adding arms by minute 17 and restored by minute 21. The final TP windows had their own shorter request cutoffs. Cache windows used a 30-minute hard restore deadline and stopped starting new work by minute 24, with extra time reserved for probes and restoration. Preserve a deadline that fits the tested rig and never start a request that cannot finish inside the budget. A rejected/censored arm is not a measured failure of engine performance.

Require **at least 300 MiB free on each GPU** in the final cache windows; abort if that floor fails. X4 retained the tested 828 MiB later-card reservation. TP proper-fit trials used 36 GiB expert RAM and 640 MiB arena reserve; increasing expert RAM alone was not a substitute for reserve. The rig had a memory-exclusion service for a known hardware issue; its continued health was part of local restoration, not a requirement to install that service on another machine.

Watch GPU temperature (historical abort above 85°C), uncorrected ECC, kernel Xid and engine non-finite, CUDA or ring errors throughout. Unavailable kernel logs are a failed health check, not a clean bill of health. Stop on the first correctness/health failure; do not continue unsafe optional arms. Budget host RAM for model weights, pinned buffers and parked copies, with room for the OS. Do not reduce firmware, thermal or memory protections to obtain a speed figure.

After every window, stop the candidate, restore the original service and verify its launcher digest, binary/profile choice, memory-exclusion service where applicable, usable GPU memory and an exact two-output request through the normal application path. Check that no candidate process remains. Record passed, failed and not-run checks separately. A completed restoration is independent of whether the experiment qualified.
