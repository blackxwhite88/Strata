# Strata (Rig Fork)

This repository is a specialized fork of [Strata](https://github.com/niko1221/strata) (MIT License), maintained and configured specifically for our dedicated local dual-GPU server rig.

For the original upstream documentation, official binary packages (Windows installer, macOS DMG, Linux AppImage), and multi-platform guides (Apple Silicon Metal, AMD ROCm/HIP, Intel Arc SYCL), see [docs/UPSTREAM-README.md](docs/UPSTREAM-README.md) or the [upstream Strata repository](https://github.com/niko1221/strata).

---

## Hardware Target

This fork is deployed and tuned for:
- **GPUs**: 2x NVIDIA GeForce RTX 2080 Ti (22 GB modified VRAM per card, 44 GB total VRAM), Turing architecture (`sm_75`).
- **Operating System**: Ubuntu Linux (x86_64).
- **Engine Version**: Strata Engine 0.1.59.1.
- **Model**: `Qwen3.8-Flash-Next Heretic V2 IQ4_XS` (`Swift-1.5-Qwen3.8-Flash-Next-Heretic-V2-IQ4_XS`, serving alias `qwen3.8-flash-next-unsloth-ud-iq4_xs`).

---

## Production Serving Topology

Production inference is arranged in a two-tier local service topology:
- **Reverse Proxy**: Listens on port `18081` in front of the engine, routing requests and providing operational buffering.
- **Strata Engine**: Listens on port `18080`.
- **Network Interface**: Bound strictly to loopback (`127.0.0.1`) only, ensuring no unauthenticated public exposure.
- **API Surface**: OpenAI- and Anthropic-compatible chat completion endpoints.

---

## Production Recipes

The rig operates under two defined operational recipes:

### 1. `2x256k` (Primary Production Recipe)
- **Concurrency**: 2 parallel live streams up to 262,144 (256k) context per slot (`--batch 2`, `--max-context 262144`).
- **Conversation Cache**: 16 parked conversation slots backed by 64 GB cache allocation (`--conversation-cache-mib 65536`, `--conversation-cache-slots 16`).
- **GPU Distribution & Quantization**: Layer split 23 across the dual GPUs (`--layer-split 23`), INT8 KV cache (`--kv int8`), trimmed stage weights (`--trim-stage-weights`).
- **Execution & Speculation**: Speculative draft verification (`--spec 3`), batched MTP drafting (`--batch-mtp`), and pipelined execution windows (`pipeline_windows=1`).

### 2. `4x128k` (High-Concurrency Recipe)
- **Concurrency**: 4 parallel live streams up to 131,072 (128k) context per slot for higher concurrency workloads.
- **Execution**: Shares the same numerical stabilization parameters as `2x256k`.

---

## Numerical Stability & NaN Fixes

Serving deep-context models on Turing GPUs previously accumulated non-finite logits (`#879`), causing dropped sessions and full re-evaluation retries (`#3465`). Rig bisection isolated four compounding failure mechanisms and established the four configuration settings that cure them:

| Failure Mechanism | Root Cause on Turing (`sm_75`) Hardware | Curing Setting |
|---|---|---|
| **1. Prompt-Tail Verify Failures** | `--short-read 64` stops chunked prefill early and evaluates prompt tails inside speculative verify windows (`Verifier::run`), triggering non-finite logits at deep context (>140k–180k tokens). | `short-read=0` (or `--short-read 0`) |
| **2. Tensor Core Overflow** | `STRATA_BF16_TC=1` downcasts BF16 matrix operations onto Turing FP16 tensor cores, overflowing the 65,504 FP16 maximum representable finite limit during long-context recurrence. | `STRATA_BF16_TC=0` |
| **3. Shared Scratch Buffer Contention** | `STRATA_PF_HC_REGION=1` and `STRATA_PF_GROUP_SCRATCH=1` share scratch regions across batch slots, creating memory race conditions when concurrent slot admissions overlap with active decodes. | `STRATA_PF_HC_REGION=0`<br>`STRATA_PF_GROUP_SCRATCH=0` |
| **4. Fused GDN Conv+L2 Normalization** | `STRATA_GDN_CONVL2=2` (or `=1`) enables a fused warp-reduction kernel marked AMD-only in engine source (`engine/src/core/arch_defaults.cpp`). On NVIDIA CUDA sm_75, it induces numerical instability in the first decode window (row 0). | `STRATA_GDN_CONVL2=0` |

Full engineering analysis, failure log traces, and candidate bisection data are documented in [docs/rig/strata-nan-stability-2026-11-21.md](docs/rig/strata-nan-stability-2026-11-21.md).

---

## Measured Performance & Stability Results

On the stabilized `2x256k` production recipe, benchmark verification and soak testing demonstrated zero numerical failures while maintaining full engine throughput:

- **128k Context Prompt Prefill**: ~2,000 tok/s (~1,770–1,970 tok/s across all context ranges up to 200k).
- **Solo Long-Context Decode (200k–240k context)**: 46–57 tok/s.
- **Concurrent Overlapping Decode**: 62–86 tok/s across mixed short and medium concurrent slots (e.g. 71–72 tok/s on a 30k slot while decoding an overlapping 8k/2k slot).
- **Stress Soak Verification**: 31 of 31 requests completed successfully (100% success rate, HTTP 200) with **zero (0) new non-finite logit lines** (`#879`).

---

## Verification & Rollback Procedures

### Health & Stress Verification
1. **Stress Test Execution**:
   ```bash
   python3 ~/bisect-nan/strata_nan_stress.py --url http://127.0.0.1:18081/v1
   ```
2. **Log Verification**:
   Ensure zero occurrences of non-finite logits during or after inference:
   ```bash
   grep -c "non-finite" /home/<rig-user>/strata-prod/r2-state/state/strata/launch/ud-iq4_xs-256k.engine.log
   ```
3. **Recipe Validation**:
   ```bash
   ~/strata-prod/verify.sh 2x256k
   ```

### Rollback Procedures
To revert to a previous recipe revision:
- **Automated Rollback**:
  ```bash
  ~/strata-prod/rollback.sh
  ```
- **Manual Restoration**:
  ```bash
  cp ~/strata-prod/recipes/2x256k.conf.pre-convl2-20261121 ~/strata-prod/recipes/2x256k.conf
  ~/strata-prod/switch-recipe.sh 2x256k
  ```

---

## Upstream Changes & Attribution

- **Upstream Project**: Created by Niko Veit and contributors under the [MIT License](LICENSE).
- **Upstream Documentation**: [docs/UPSTREAM-README.md](docs/UPSTREAM-README.md).
- **Upstream Repository**: [https://github.com/niko1221/strata](https://github.com/niko1221/strata).
- For pre-built desktop packages, multi-platform releases, or reporting upstream engine bugs, please refer directly to the upstream repository.
