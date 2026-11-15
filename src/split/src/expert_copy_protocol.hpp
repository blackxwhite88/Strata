// Single-producer (decode stream), single-consumer (host worker) mailbox.
// No cross-processor read/modify/write atomics: only aligned 32-bit loads/stores.
#pragma once

#include <cstddef>

namespace fnx {
constexpr int EXPERT_COPY_CAP = 160;  // MAXT * TOPK, checked by the engine
struct alignas(64) ExpertCopyRequest {
    alignas(64) volatile unsigned issued = 0;
    alignas(64) volatile unsigned done = 0;
    unsigned status = 0;
    int layer = 0, count = 0;
    int expert[EXPERT_COPY_CAP] = {};
    char* dst[EXPERT_COPY_CAP] = {};
    unsigned long long timeout_ticks = 0;
};

inline unsigned copy_request_load(const volatile unsigned* p) { return __atomic_load_n(p, __ATOMIC_ACQUIRE); }
inline void copy_request_store(volatile unsigned* p, unsigned v) { __atomic_store_n(p, v, __ATOMIC_RELEASE); }
}  // namespace fnx
