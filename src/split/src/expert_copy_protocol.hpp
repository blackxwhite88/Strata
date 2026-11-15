// Single-producer (decode stream), single-consumer (host worker) mailbox.
// No cross-processor read/modify/write atomics: only aligned 32-bit loads/stores.
#pragma once

#include <cstddef>

namespace fnx {
constexpr int EXPERT_COPY_CAP = 160;  // MAXT * TOPK, checked by the engine
struct alignas(64) ExpertCopyRequest {
    alignas(64) volatile unsigned issued = 0;
    alignas(64) volatile unsigned done = 0;
    volatile unsigned status = 0;
    int layer = 0, count = 0, prefetch = 0;
    int expert[EXPERT_COPY_CAP] = {};
    char* dst[EXPERT_COPY_CAP] = {};
    unsigned long long timeout_ticks = 0;
};

// Shared by the CUDA publisher and the CPU selection test. Invalid probe values
// (including an all-nonfinite row's sentinel) never become an expert address.
#if defined(__CUDACC__)
__host__ __device__
#endif
inline int copy_missing_guesses(const int* guess, int n, int base, int nexp, const int* slot_of, int* out) {
    int count = 0;
    for (int i = 0; i < n && count < EXPERT_COPY_CAP; ++i) {
        const int e = guess[i];
        if (e < 0 || e >= nexp || slot_of[e] >= 0) continue;
        bool seen = false;
        for (int j = 0; j < count; ++j) seen |= out[j] == base + e;
        if (!seen) out[count++] = base + e;
    }
    return count;
}

inline unsigned copy_request_load(const volatile unsigned* p) { return __atomic_load_n(p, __ATOMIC_ACQUIRE); }
inline void copy_request_store(volatile unsigned* p, unsigned v) { __atomic_store_n(p, v, __ATOMIC_RELEASE); }
}  // namespace fnx
