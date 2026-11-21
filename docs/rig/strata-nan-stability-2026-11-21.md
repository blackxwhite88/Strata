# Strata Production Numerical Stability & Non-Finite Logits (NaN) Fix — 2026-11-21

**Host**: `<rig-user>@<rig-host>` (2x RTX 2080 Ti 22 GB, Turing sm_75)  
**Service**: Strata Engine 0.1.59.1 (port 18080, proxy port 18081)  
**Model**: `Swift-1.5-Qwen3.8-Flash-Next-Heretic-V2-IQ4_XS` (serving alias `qwen3.8-flash-next-unsloth-ud-iq4_xs`)  
**Active Recipe**: `~/strata-prod/recipes/2x256k.conf`  
**Related Investigation**:
- Phase A Investigation (Log quantification and failure episode categorization)
- Phase B Bisection (Candidate testing B1–B5 on rig)
- Bisect-3 Follow-Up (Candidate testing C1–C5 on rig)

---

## Executive Summary

Prior to 2026-11-21, production serving under the `2x256k` recipe accumulated **575 non-finite logit lines** (`#879`) across **5 distinct operational episodes** in the engine log (`/home/<rig-user>/strata-prod/r2-state/state/strata/launch/ud-iq4_xs-256k.engine.log`). These failures manifested primarily in prompt evaluation windows, first decode windows, and decode steps, forcing full session drops and fallback retries (`#3465`).

Through multi-phase controlled bisection and stress testing on the rig, the failures were traced to **four independent compounding mechanisms**:
1. Speculative evaluation of prompt tails in verify windows when `--short-read` is non-zero.
2. Numerical overflow (>65,504) from downcasting BF16 matrix operations onto Turing sm_75 FP16 tensor cores (`STRATA_BF16_TC=1`).
3. Memory race conditions in shared prefill head-chunk and group scratch buffers under multi-slot concurrency (`STRATA_PF_HC_REGION=1`, `STRATA_PF_GROUP_SCRATCH=1`).
4. Numerical instability in the fused GDN convolution + L2 normalization warp-reduction kernel (`STRATA_GDN_CONVL2=2`), which engine source marks AMD-only.

On 2026-11-21, production configuration `~/strata-prod/recipes/2x256k.conf` was updated in two stages:
- **Change 1 (B4 baseline)**: `STRATA_BF16_TC=1->0`, `STRATA_PF_HC_REGION=1->0`, `STRATA_PF_GROUP_SCRATCH=1->0`, added `short-read=0`.
- **Change 2 (ConvL2 fix)**: `STRATA_GDN_CONVL2=2->0`.

Post-change soak testing with 31 heavy concurrent and deep-context requests completed with **31 of 31 requests OK (100% success)** and **0 new non-finite lines**. Prefill throughput reached ~2,000 tok/s at 128k context, and decode throughput sustained 46–86 tok/s across all concurrency levels.

---

## (a) Root Causes, Evidence, and Remediation

### 1. Short-Read Prompt Tail Verify Window Failure

- **Plain Engineering Explanation**:
  By default, `--short-read 64` directs the chunked prefill engine to stop up to 64 tokens short of the total prompt length, delegating the remaining prompt tail tokens to the speculative verify window (`Verifier::run`). When evaluating deep prompts (>140k–180k tokens) or during concurrent multi-slot admissions, evaluating prompt tails inside `Verifier::run` triggers non-finite logits (`#879`). This wipes the active session state and triggers an internal engine recovery (`#3465`) that re-reads the prompt from token 0.
- **Observed Evidence**:
  - The production engine log contained 228 lines of `non-finite logits (#879) in a prompt window` and 113 matching `#3465` fallback recovery lines.
  - Rig bisection reproduced this failure mode cleanly on candidate `B1-bf16-tc-0` at position 180,038 (prompt length 180,045; tail 7 tokens) and candidate `B5-solo-ref` at position 180,038. In both reproductions, recovery `#3465` forced `--short-read 0` for the retry, and the exact same prompt read via batched chunk prefill immediately succeeded with 0 NaNs.
- **Curing Setting**:
  `short-read=0` (passed as `--short-read 0`). Forces 100% of prompt tokens through the chunked prefill engine, bypassing speculative verify windows on prompt tails.

### 2. BF16_TC Downcast to FP16 on Turing (sm_75) Tensor Cores

- **Plain Engineering Explanation**:
  NVIDIA Turing architecture GPUs (sm_75, RTX 2080 Ti) possess FP16, INT8, and INT4 tensor cores, but lack native hardware BF16 tensor cores (introduced in Ampere sm_80). Setting `STRATA_BF16_TC=1` causes the engine to downcast BF16 matrix multiplications into FP16 tensor core operations. FP16 uses a 5-bit exponent with a maximum finite representable value of 65,504 (compared to BF16's 8-bit exponent with max finite range ~3.4e38). During deep-context processing (>96k tokens), Gated Delta Net (GDN) recurrent state accumulation and attention projections exceed 65,504, causing floating-point overflow (`inf`/`NaN`) during the first decode window or solo decode.
- **Observed Evidence**:
  - Production Episode 3 occurred with a single isolated request in flight (solo path `GEN`, position 30,391, 0 other running slots, 147 generated tokens) where logits abruptly blew up with `#879`.
  - On rig candidate `B2-short-read-0` (where `short-read=0` eliminated prompt-window NaNs, but `STRATA_BF16_TC=1` remained active), a 128k prompt cleanly finished prefill of 96,045 tokens, but immediately failed at position 96,044 (row 0) in the first decode window (`Verifier::run`).
- **Curing Setting**:
  `STRATA_BF16_TC=0`. Disables downcasting to FP16 tensor cores on Turing sm_75, preserving numerical headroom.

### 3. Shared HC / Group Scratch Buffer Race Under Concurrency

- **Plain Engineering Explanation**:
  `STRATA_PF_HC_REGION=1` and `STRATA_PF_GROUP_SCRATCH=1` enable shared scratch buffer allocations across batch slots for prefill head chunks and group operations. Under multi-slot concurrency, an incoming prompt admission races with an active decode step in another slot, clobbering intermediate scratch memory and corrupting active tensors.
- **Observed Evidence**:
  - Production Episodes 1, 2, 4, and 5 occurred exclusively under multi-slot concurrency (e.g. Episode 2 at position 142,065 during active slot 1 decode at 70,042 tokens; Episode 5 retry cascade under concurrent slot admissions).
  - Allocating isolated per-stream scratch buffers (`STRATA_PF_HC_REGION=0` and `STRATA_PF_GROUP_SCRATCH=0`) eliminated memory contention across concurrent slots without throughput penalty.
- **Curing Setting**:
  `STRATA_PF_HC_REGION=0` and `STRATA_PF_GROUP_SCRATCH=0`.

### 4. GDN_CONVL2 Fused Kernel (Marked AMD-Only in Engine Source)

- **Plain Engineering Explanation**:
  In Gated Delta Net (GDN) recurrence, convolution and L2 normalization of query ($q$) and key ($k$) projections prepare the recurrent state for attention score calculation. In canonical Strata (`STRATA_GDN_CONVL2=0`), convolution (`gdn_conv_tiled_kernel`) and L2 normalization (`gdn_l2_kernel`) are evaluated as separate kernel passes using standard FP32 reduction trees.
  When `STRATA_GDN_CONVL2=2` (or `=1`) is enabled, the kernel fuses convolution, SiLU activation, and $q/k$ L2 norm into a single warp-reduction pass (`gdn_conv_w_kernel` in `engine/src/prefill/kernels.cu`). As explicitly documented in engine source `engine/src/core/arch_defaults.cpp:38-40`:
  > *"STRATA_GDN_CONVL2 is AMD-only on purpose: it is not bitwise on CUDA 13.3 sm_120 (#1522), and this table is never consulted by a CUDA build."*
  On NVIDIA CUDA (sm_75), running this non-bitwise fused kernel leads to numerical instability and non-finite logits in first decode windows under deep context or multi-turn workloads.
- **Observed Evidence**:
  - Production engine log line 15464 recorded: `strata serve: non-finite logits (#879) in a first decode window at position 22543 (row 0)`.
  - Replicated on rig candidate C4b (`STRATA_GDN_CONVL2=1`) at position 150,044 (row 0) in the first decode window during solo 200k testing. Disabling the fused kernel in Candidate C4a (`STRATA_GDN_CONVL2=0`) ran 16 stress rounds (31 requests) with 0 NaNs.
- **Curing Setting**:
  `STRATA_GDN_CONVL2=0`. Forces the engine to use standard separated convolution and L2 normalization kernels with standard FP32 reduction trees.

---

## (b) Live Recipe Delta Table (`2x256k.conf`)

Production configuration `~/strata-prod/recipes/2x256k.conf` was modified twice on 2026-11-21. The table below details the progression from the pre-bisect baseline to the current rocksolid configuration:

| Setting / Variable | Pre-2026-11-21 Baseline | Step 1 (B4 Baseline) | Step 2 (Current Live) | Engineering Rationale |
|---|---|---|---|---|
| `STRATA_BF16_TC` | `1` | `0` | `0` | Prevents FP16 tensor core overflow (>65,504) on Turing sm_75 |
| `STRATA_PF_HC_REGION` | `1` | `0` | `0` | Eliminates shared prefill head-chunk buffer race across slots |
| `STRATA_PF_GROUP_SCRATCH` | `1` | `0` | `0` | Eliminates shared group scratch buffer race under concurrency |
| `short-read` | `64` (engine default) | `0` (added) | `0` | Eliminates speculative verify window failures on prompt tails |
| `STRATA_GDN_CONVL2` | `2` | `2` | `0` | Disables AMD-only fused warp-reduction kernel; uses bitwise-exact separated FP32 kernels |

### Backup File Inventory on Rig
- Original pre-bisection recipe backup:  
  `~/strata-prod/recipes/2x256k.conf.pre-b4-20261121`
- Intermediate post-B4 recipe backup:  
  `~/strata-prod/recipes/2x256k.conf.pre-convl2-20261121`
- Active production recipe:  
  `~/strata-prod/recipes/2x256k.conf`

---

## (c) Verification and Rollback Procedures

### 1. Stress Verification Tooling & Execution

Stress verification is driven by the Python harness on the rig: `~/bisect-nan/strata_nan_stress.py`.

```bash
# Execute stress test against the production proxy endpoint (port 18081)
python3 ~/bisect-nan/strata_nan_stress.py --url http://127.0.0.1:18081/v1
```

#### Workload Composition (31 Total Requests):
1. **Concurrency Overlap (12 rounds = 24 requests)**:
   - Primary request: ~30,000 tokens prompt.
   - Secondary request: ~8,000 tokens prompt admitted during primary decode.
2. **Deep Concurrency Overlap (3 rounds = 6 requests)**:
   - Primary request: ~128,000 tokens prompt.
   - Secondary request: ~2,000 tokens prompt admitted during primary decode.
3. **Deep Solo Long-Context (1 round = 1 request)**:
   - Solo request: ~200,000 tokens prompt.

### 2. Log Verification & Non-Finite Line Counting

The production engine log is located at:
```bash
/home/<rig-user>/strata-prod/r2-state/state/strata/launch/ud-iq4_xs-256k.engine.log
```

To verify numerical stability during and after stress testing, count occurrences of `non-finite`:
```bash
grep -c "non-finite" /home/<rig-user>/strata-prod/r2-state/state/strata/launch/ud-iq4_xs-256k.engine.log
```
Or monitor live output for `#879` events:
```bash
tail -F /home/<rig-user>/strata-prod/r2-state/state/strata/launch/ud-iq4_xs-256k.engine.log | grep --line-buffered "non-finite"
```

#### Benchmark Verification Results (Post-Change Soak):
- **Request Success**: 31 of 31 requests completed successfully (HTTP 200).
- **New Non-Finite Lines**: **0** (Zero NaNs).
- **Prefill Throughput**: ~2,000 tok/s at 128k context (~1,770–1,970 tok/s across all context ranges).
- **Decode Throughput**: 46–86 tok/s across concurrent decode and long-context solo steps.

### 3. Rollback Procedures

If rollback to earlier recipe revisions is required:

#### Option A: Automated Rollback Script
```bash
~/strata-prod/rollback.sh
```

#### Option B: Manual Backup Restoration
```bash
# To rollback to the pre-convl2 state:
cp ~/strata-prod/recipes/2x256k.conf.pre-convl2-20261121 ~/strata-prod/recipes/2x256k.conf
~/strata-prod/switch-recipe.sh 2x256k

# Or to rollback to the initial pre-b4 state:
cp ~/strata-prod/recipes/2x256k.conf.pre-b4-20261121 ~/strata-prod/recipes/2x256k.conf
~/strata-prod/switch-recipe.sh 2x256k
```

#### Post-Rollback Service Health Check:
```bash
~/strata-prod/verify.sh 2x256k
systemctl --user is-active gpu0-quarantine.service
journalctl -k --since "5 minutes ago" | grep -E "Xid|ECC"
```

---

## (d) Open Items & Operational Recommendations

1. **Recipe Alignment for `4x128k`**:
   The `~/strata-prod/recipes/4x128k.conf` recipe currently retains legacy defaults. The same five stabilization settings (`STRATA_BF16_TC=0`, `STRATA_PF_HC_REGION=0`, `STRATA_PF_GROUP_SCRATCH=0`, `short-read=0`, `STRATA_GDN_CONVL2=0`) should be applied to `4x128k.conf`, followed by an equivalent 31-request soak test prior to production promotion.
2. **Periodic Non-Finite Logit Alert**:
   Deploy a periodic timer (e.g. systemd timer or cron) monitoring `/home/<rig-user>/strata-prod/r2-state/state/strata/launch/ud-iq4_xs-256k.engine.log` for any new occurrences of `non-finite logits (#879)`, providing immediate notification if numerical regression occurs.
3. **Rig Root Disk Space Management**:
   The rig root disk currently operates with limited free margin (~14 GB free, 94% utilization). Safe cleanup candidates:
   - Stale launcher logs matching `start-out-*.log` under `~/strata-prod/` or state paths.
   - Bisect run state directories under `~/bisect-nan/` (e.g. `~/bisect-nan/state/`).
   - Superseded recipe backups (`2x256k.conf.pre-b4-20261121`, `2x256k.conf.pre-convl2-20261121`) after a one-week retention window.
4. **Stress Test Script Location**:
   The stress test harness is maintained directly on the rig filesystem at `~/bisect-nan/strata_nan_stress.py`.
