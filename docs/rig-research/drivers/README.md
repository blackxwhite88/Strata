# Benchmark sources

The [archive manifest](archive/manifest.json) identifies twelve actual window-driver variants and their original source SHA256 digests. Files are sanitized AST exports: comments/docstrings were removed, local paths/endpoints and model-pack names replaced, and embedded prompt content omitted. `fixtures()` and `suffix()` helpers are disabled where present. Every archived module raises before doing any work, even when imported. The source digests describe the originals; the sanitized files have different bytes.

| Source group | Preserved drivers | Scope |
| --- | --- | --- |
| First and second TP windows | `window-original.py`, `window2.py` | S1/S2/S3 triggers, health, guard, restoration |
| Third and fourth TP windows | `window3.py`, `window4.py` | Sequential reuse, paired reuse assertion, host-probe invocation |
| Final TP/native comparison | `final.py`, `final-B.py`, `r2-retry.py` | Flag arms, paired histories, third read, sustained leg, host-probe invocation |
| R2 byte-budget trial | `x-window.py`, `x-window2.py` | Initial and corrected runtime identity check, R2/R3 comparison |
| R2 entry-count and final recipes | `x-window3.py`, `x-window4.py`, `x-window5.py` | Entry retention, rotations, RAM/VRAM snapshots and loss checks |

No original executable driver was present in the supplied overnight or decode-validation report directories. The first TP window's evidence directory contained outputs but no driver; its original source survived in the second window's `window-original.py` copy. The CPU-copy probe itself was not present in these window directories, only its invocation/parser. Those missing sources are not reconstructed and presented as originals. No evidence archives, logs, prompts or fixtures are copied.

Review archived guard, request, group and probe logic as a record of the experiments. Adapting an archived lifecycle driver requires new paths, endpoint configuration, synthetic input generation, process ownership checks, saved service identity and a separately tested restoration guard. Removing its first exception alone does not make it runnable. Historical digest checks and ports belong to their original windows.

## Portable request measurement

[measure.py](measure.py) is a new portable adapter derived from the final cache-window request/group logic. It uses only the Python standard library, sends requests to an already running local candidate and saves numeric timing fields and input/output hashes. It does not retain request or generated text. If authentication is required, it reads `RIG_API_KEY` from the environment and does not persist it. It never starts, stops or restores a server and does not substitute for the [method's](../METHOD.md) external health/restore guard.

Provide a JSON list of role/content messages for each newly generated synthetic history. Use different nonces near the first user content, hold each history fixed during its rounds and leave enough context for the suffix and reply. Original fixture text and greedy hashes are unavailable. The driver primes each history sequentially, then submits all histories together for three rounds. Histories should end in the same role/history shape in each arm; reuse of a fixed base plus fresh suffix tests repeated continuations/rewinds, not an indefinitely growing chat.

```sh
python3 docs/rig-research/drivers/measure.py --help
python3 docs/rig-research/drivers/measure.py \
  --base-url "$BENCH_API_BASE" --model qwen3.8 \
  --messages "$SYNTHETIC_HISTORY_1" "$SYNTHETIC_HISTORY_2" \
  --outputs 512 --rounds 3 --seed 40261114 --min-cache-n 190000 \
  --output "$BENCH_RESULT_DIR/two-stream.json"
```

Set the API base to the candidate's local API root ending in `/v1`. For four ~128k histories, supply four files and use a threshold such as 120000. For shorter diagnostic histories choose a measured threshold appropriate to their size. A missing engine `cache_n` fails the warm check rather than silently qualifying a run. Verify that the primes actually read cold using their saved numeric timings; a pre-existing cache can make a nominal prime warm.

The adapter checks completion counts, end-of-stream, timing intervals and warm-prefix thresholds. It has a request socket timeout and checks elapsed time between received lines; an external process timeout and hard restore deadline are still required. HTTP failures save a generic failure status and completed groups without including remote error text. It records chunk-level emission rates, engine rates, TTFT, gaps and whole-request throughput separately. It does not check synthetic markers, exact engine identity, GPU health, state classification, admission fairness or sustained retention. Perform those checks independently before accepting a recipe or performance claim. Two identical files are rejected, but distinct file digests do not prove independent prefixes; inspect the generated inputs locally.

## Local validation of this export

The documentation export was checked by parsing/compiling every supplied Python source without running archival code, exercising the portable adapter against a local synthetic SSE test service, checking local Markdown targets, comparing retained result-table rows to their source exports, checking recipe values against the final drivers, and running the scrub scans in [SANITIZATION.md](../SANITIZATION.md). No GPU benchmark, service restart, backend build or remote operation was performed for this export.
