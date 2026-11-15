# Tested native serving recipes

R2 is the native layer-split configuration with stage trimming and piped MTP drafting. Both final candidates use int8 KV, vision enabled, MTP spec=3, 32768 resident KV positions, a 65536 MiB (64 GiB) conversation cache and twelve parked entries. Live decode slots and parked cache entries are different resources.

These are the settings measured on modified 22 GB RTX 2080 Ti cards with about 247 GB host RAM. They are opt-in examples, not new Strata defaults or a promise of fit on stock cards. A 256k or 128k ceiling includes the entire conversation and reply. The two-stream validation used approximately 200k histories. No full-length 256k input or long unattended soak was established by the final window.

## Identity and common settings

The native runs recorded engine version 0.1.59 (patch 1) and SHA256 `4f7ad93a13360398b0f97c7161c4b779c7125217e63f77a0abc0fde04add9c66` from the upstream `13eedf55` source line (engine 0.1.59). The TP guard lineage is `6dd2cdd9` → `3f38fd86` → `457507df`. The later TP speed experiments are separate; they are not dependencies of R2. A new build will have its own digest and must be retested.

The measured native process required CUDA 13.3 runtime libraries. Put their installation's library directory on `LD_LIBRARY_PATH` for the candidate process if necessary. Merely using a CUDA 12.4 TP build is not the same engine. The original launcher placed its own directory first in the runtime search path, so identity checks must verify availability and loaded binary rather than demand one arbitrary directory ordering.

Supply `MODEL_PATH` as `<model path>` and `MODEL_DATA_DIR` as the model support-data directory. The model pack's exact file layout is omitted. Clear inherited experiment settings and use isolated `XDG_STATE_HOME`, `STRATA_PROFILE_DIR` and `STRATA_RUNTIME_DIR` directories outside the checkout. A saved profile can override expectations. Both commands select the model family explicitly and keep access local.

The common native settings passed through `--set` were:

```text
STRATA_BF16_TC=1
STRATA_GDN_CONVL2=2
spec=3
pipeline_windows=1
STRATA_PF_GROUP_SCRATCH=1
STRATA_PF_HC_REGION=1
layer-split=23
trim-stage-weights=1
STRATA_STAGE_TRIM=1
batch-mtp=1
STRATA_PIPED_MTP=1
STRATA_BATCH_SELF_COMMIT=0
STRATA_PIPED_CONCURRENT=0
STRATA_SM75_PERF=0
prefill-pipe=0
conversation-cache-mib=65536
conversation-cache-slots=12
```

The launcher's tested process selected `--kv-resident 32768`; confirm it in the plan and actual argv. This is a count of positions, not a 32 GiB cache. The `STRATA_*` entries above are engine environment settings carried by `--set`; the other entries are engine options. Do not turn them all into shell environment variables.

## Two live streams, 256k ceiling

```sh
strata launch --family unsloth --model ud-iq4_xs \
  --model-path "$MODEL_PATH" --data-dir "$MODEL_DATA_DIR" \
  --context 256k --parallel 2 --kv int8 --vision on --drafting mtp \
  --access local --port 18082 --tune skip --split-engine off --yes --no-tui \
  --set STRATA_BF16_TC=1 --set STRATA_GDN_CONVL2=2 \
  --set spec=3 --set pipeline_windows=1 \
  --set STRATA_PF_GROUP_SCRATCH=1 --set STRATA_PF_HC_REGION=1 \
  --set layer-split=23 --set trim-stage-weights=1 --set STRATA_STAGE_TRIM=1 \
  --set batch-mtp=1 --set STRATA_PIPED_MTP=1 --set STRATA_BATCH_SELF_COMMIT=0 \
  --set STRATA_PIPED_CONCURRENT=0 --set STRATA_SM75_PERF=0 --set prefill-pipe=0 \
  --set conversation-cache-mib=65536 --set conversation-cache-slots=12
```

Port 18082 is an example candidate port, not a requirement for production. Run with `--plan` first, inspect the result, then run the measured candidate under the restore guard. The tested two-slot process had no `vram-reserve-later-mib` override.

[X5](reports/strata-r2-x5.md) primed three independent ~200k histories, exercised two active streams, checked all three for loss, then ran five more pairs. All twenty continuations hit. Three cold primes took 124.5 / 129.8 / 128.9 s to first output. Single-stream decode was 62.9 tok/s; paired per-stream decode averaged 27.4 early and 26.5 in the sustained leg. Those paired sums were 54.7 and 53.0 tok/s; whole-request throughput was 40.0 and 36.6 respectively. Cached first-output waits were still 2.6–12.8 s.

Peak parked-cache usage was 41.75 GiB; available host RAM fell from 170.1 to 127.9 GiB. Free VRAM stayed above 552 / 404 MiB, with a required 300 MiB floor on each card. Twelve entries filled and eight evictions followed. The idle third history was not checked after that sustained churn. This recipe supports the tested two-active workload; it does not guarantee indefinite retention of an idle third history.

## Four live streams, 128k ceiling

Use the same common settings, with these three changes:

```text
--context 128k
--parallel 4
--set vram-reserve-later-mib=828
```

For example, substitute those values in the two-stream command and keep all other settings. The live engine must show `--batch 4 --max-context 131072 --kv-resident 32768 --vram-reserve-later-mib 828`. The 828 MiB later-card reserve is part of the tested fit; keep it.

[X4](reports/strata-r2-x4.md) retained all twenty continuations across four independent ~128k histories, rotations and a final loss check. Cold primes took 70.4–75.0 s each. Four-stream whole-request throughput was 52.3 / 53.5 tok/s early and 28.7 later, with per-stream decode ranging 7.5–21.5 in the 512-output groups. These figures use a different metric and workload from X5's decode sums. Cached first-output waits were 2.3–19.6 s.

Peak parked-cache usage was 28.38 GiB; available host RAM fell from 172 to 143 GiB. Free VRAM stayed above 494 / 440 MiB. Twelve entries filled and four evictions occurred. The final check still hit all four histories, but the evicted entry identities were not logged. There is little context room: ~128.5k input plus 512 reply positions left only about 2k below 131072. Count history growth, tool content and images before sending another turn.

## Why these settings, and what remains open

Stage trimming avoids duplicate stage weights. Piped MTP keeps drafting active with multiple native slots; `STRATA_BATCH_SELF_COMMIT=0` is part of that tested path. Larger conversation caches avoid repeated long cold reads, but each continuing conversation can leave several parked entries. Twelve is the tested count. Sixteen entries at the same 64 GiB budget was suggested after X4/X5; it was not load-tested in either final window. The later deployment verified startup and short-prefix reuse with sixteen, as described below. X5's rough 55 GiB estimate for sixteen full entries is an estimate, not a RAM qualification.

Keep R3 (`STRATA_PIPED_CONCURRENT=1`) off. Its long concurrent read failed with non-finite logits and invalidated cached state. Keep prefill-pipe and the SM75 performance suite off in this recipe. TP copy-engine, counter, prefetch and read-interleave switches belong to the separate TP experiments and are not R2 settings. Prefetch hurt the final observed TP configuration. A relay was not implemented or measured because the layer-split byte accounting offered no useful saving.

Unverified: other cards, stock 11 GB cards, another model/quantization, complete 256k histories, lengthy growing conversations, image/tool-heavy cache churn, retention after many idle-history evictions, load at sixteen entries, unattended operation and corrected R3 concurrency. Vision stayed enabled, but the final cache windows used text; the older image battery does not qualify every final recipe's image behavior.

## Subsequent production application

The [application report](reports/strata-prod-r2-apply.md) records installation at 15:45–15:52 UTC on 15 November. The default running mode became two streams at 256k, and switching to four at 128k and back was verified. Both installed profiles raised `conversation-cache-slots` from 12 to **16**, retaining the same 65536 MiB budget. That is a deployment choice beyond the load-tested commands above.

Live checks confirmed the binary digest, slot/context/cache settings, at least 300 MiB free per card and a two-output request in both modes. A ~32k continuation reused 32768 positions with only 277 newly read positions in the two-stream mode, including after switching back. These checks do not establish sixteen-entry long-history retention, four-way sustained throughput or full-context image behavior. A fixed byte ceiling also does not mean twelve and sixteen entries use identical resident RAM at every instant. The startup script remembered the selected profile; automatic service startup after a reboot was not configured.

The application report's rollback was syntax-checked but **not exercised**. Preserve that limit when reusing its design. The private deployment scripts are not copied into this public bundle.

## Roll back completely

Before a window, save the existing launcher, binary/component selection, saved profile, environment and their checksums outside the checkout. Arm a separate local guard that can stop only the candidate, restore those saved choices, and restart the original launcher by a hard deadline. Test that guard before stopping an existing service.

Stop the candidate through its own isolated launch state. Restore the entire saved launcher and component/profile selection, then invoke the unchanged original launcher once. Confirm its digest, expected process identity, any rig-specific memory-exclusion service, usable GPU memory and a two-output completion through the ordinary application endpoint. A successful model load alone is insufficient. Reverting only the added flags while retaining a different binary or saved profile is incomplete rollback. This documentation bundle performs no service operation.
