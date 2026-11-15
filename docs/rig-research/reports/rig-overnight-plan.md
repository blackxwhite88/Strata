# Rig overnight plan

Sanitized, abridged historical report; November 2026. Result tables below are retained from the source report. No measurements were rerun for this export. Raw logs, request text and fixtures are omitted.

Historical test plan, not evidence that every proposed phase ran or passed. Expected gains and success thresholds below are planning assumptions. Completed results and corrections appear in the overnight, validation, truth and cache reports.

## Short source excerpts

Pick the best serving recipe for our workload (Qwen3.8-Flash-Next Heretic IQ4_XS, 128k-256k context, 2 concurrent streams, long-prefix reuse, MTP/DFlash2 drafting) by measuring candidates head-to-head on the same synthetic prompts. Output: one ranked table and a recommended start script, plus a rollback to today's production script.

Phase 2 (60-90 min): Turing patch arm, Strata. Cherry-pick 6dbafa61 (native IQ prompt kernels on SM75), 7600ae34, 861fca99, d5869fc6 from Strata source onto a local Strata build under <local path> Build on the rig (CPU-heavy, no GPU needed). A/B: STRATA_PF_FUSED_NATIVE_SM75 0 vs 1. Success: prefill >= +2.5%, decode within +/-1%, VRAM within +128 MiB, identical greedy output and 3/3 needle markers at 128k.

Phase 3 (60 min): Strata attention opt-ins already in upstream: STRATA_SELECT_SIMT=2, STRATA_PA_V2T=1 (expected +2-4% prefill, summation order may change answers: check output equality).

Phase 5 (60 min): Drafting. MTP spec=3 (current) vs DFlash2 (spec 6, draft-conf 0.5) on code, prose, and 32k continuation. Fork measured +15-20% decode on code, -6% on prose; check on our rig.
