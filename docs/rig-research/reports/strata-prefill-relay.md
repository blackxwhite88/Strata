# Strata prefill relay

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

Read-only relay scout. Native R2 divides layers across cards, so each card needs different expert bytes and both links already pipeline work. A half-and-exchange relay does not reduce shared host reads. The estimated 0–3% FAST / 0% SLOW benefit is an analytical bound, not a measured relay experiment.

## Retained tables

### 1. How R2's prefill moves expert weights today

| | CUDA0 | CUDA1 |
|---|---:|---:|
| Layers (R2 log: `layer split: layers 0-22 (CUDA0), 23-47 (CUDA1)`) | 0-22 | 23-47 (+ head, draft) |
| Expert blobs it owns | 11,776 | 12,800 |
| Expert bytes it owns (pack table) | 28.44 GB | 32.10 GB |
| Expert cache slots (startup log lines 42, 49) | 6,653 | 6,116 |
| Slots the prompt path borrows (lines 56-57) | 1,609 | 1,564 |
| Resident during prefill | 5,044 | 4,552 |
| **Streamed per 8,192-token chunk, at most** | **6,732 blobs, ~16.3 GB** | **8,248 blobs, ~20.7 GB** |

### 3. Byte and time estimates, cold prefill

| | 128k FAST | 128k SLOW | 200k FAST | 200k SLOW |
|---|---:|---:|---:|---:|
| Host bytes, no relay (≤) | 591 GB | 591 GB | 924 GB | 924 GB |
| Host bytes, with relay | same | same | same | same |
| Transfer floor, no relay | ~28 s (CUDA1 link) | ~77 s (host cap) | ~44 s | ~120 s |
| Transfer floor, ideal relay | ~25 s | ~77 s | ~39 s | ~120 s |
| **Measured, R2, no relay** | **70.9-71.4 s (1,797-1,810 tok/s), 3 runs** | not measured cold | **126.2 s (1,588 tok/s), 1 run** | **186.0 s / 192.8 s (1,075 / 1,037 tok/s), 1 run** |
| **Expected with relay** | ~69-71 s (0-3%) | ~same (0%) | ~123-126 s (0-3%) | ~same (0%) |
