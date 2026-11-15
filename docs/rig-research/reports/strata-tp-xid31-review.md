# Strata tp xid31 review

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

Read-only fault analysis. Non-finite router rows could yield an out-of-range expert index by code inspection. That explains a possible downstream fault path, not the origin of non-finite values. The early source-identity concern is corrected by the later fix review.

## Retained tables

### 1. The three failures, side by side

| Run | Settings | Where it stopped | Message |
|---|---|---|---|
| Wave 2, TP128-R44 | RAM 44, peer on, prompt peer on, 2 slots | first batched window on a lane holding 128,553 tokens | `verify_rows: a ring sum met a NaN or inf (or, on the fp16 ring, a value past its range)` |
| Wave 5b primary | RAM 36, reserve 640, peer on, prompt peer on | cold read on one lane while the other decodes | `prefill: ring error 2` |
| Wave 5b PF_HOST | same, `FNX_PF_PEER=0` | same workload | `verify_rows sync: an illegal memory access was encountered`, Xid 31 on both cards |

### Where in the read each run was

| Run | Last growth logged | Growth that would come next | So it failed in |
|---|---|---|---|
| Primary | 610 -> 674 (578 slots lent) | 738, for the pass ending 114,688 | the pass 98,304 -> 106,496 |
| PF_HOST | 674 -> 738 (662 slots lent) | 802, for the last pass | passes 106,496 -> 122,880, or a window between them |
