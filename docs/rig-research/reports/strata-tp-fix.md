# Strata tp fix

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

Source changes at 3f38fd86 and 457507df guard non-finite router rows and print first-bad-row/error context. They close an out-of-range indexing path; they do not identify or repair the upstream origin of non-finite values. This report records local source validation, not a new rig run.

## Short source excerpts

1. `3f38fd86` — `[Engine] split: the router reports a row without ten finite logits instead of indexing past its tables` (C1, C2, C3 first-row record, C6).

2. `457507df` — `[Engine] split: name the lanes, pages and lent slots on a window or prompt error` (C4 and the bit-8 split).

Implemented only the requested router guards, first-row record, diagnostics and kernel regression tool. No rig operation, lending change, allocation-address log, remote publication or merge.

Both routers ignore non-finite candidates. If fewer than ten finite candidates are found, all ten picks for that row become experts 0..9 with zero weights, before any expert-indexed table or job builder uses them. Bit 32 is set. One atomicCAS per bad row claims a per-card `(path, layer, row)` record, retained for the engine lifetime, matching the sticky error word. The prompt kernel lives in `router_topk.cuh` so its production implementation can be exercised directly by the standalone test.
