// Prompt routing, also compiled directly by tools/router_guard_test.cu.
#pragma once
#include "router_guard.cuh"

namespace fnx {
namespace {
// row t (a warp): top 10 of the NEXP logits (the lower index on a tie), weights the selected softmax renormalized
__global__ void k_pf_top10(const float* __restrict__ logits, int C, int* __restrict__ topi, float* __restrict__ topw,
                            unsigned* err, RouterBadRow* bad_row, int layer) {
    const int t = blockIdx.x * (blockDim.x >> 5) + (threadIdx.x >> 5), lane = threadIdx.x & 31;
    if (t >= C) return;
    float v[NEXP / 32];
#pragma unroll
    for (int i = 0; i < NEXP / 32; ++i) v[i] = logits[(size_t) t * (NEXP + 1) + lane + 32 * i];
    unsigned taken = 0;
    bool bad = false;
    float top0 = 0.f, z = 0.f, wk = 0.f;
#pragma unroll 1
    for (int k = 0; k < TOPK; ++k) {
        float bv = -INFINITY;
        int bi = NEXP;
#pragma unroll
        for (int i = 0; i < NEXP / 32; ++i)
            if (!(taken >> i & 1u) && isfinite(v[i]) && v[i] > bv) { bv = v[i]; bi = lane + 32 * i; }
#pragma unroll
        for (int o = 16; o; o >>= 1) {
            const float ov = __shfl_xor_sync(0xffffffffu, bv, o);
            const int oi = __shfl_xor_sync(0xffffffffu, bi, o);
            if (ov > bv || (ov == bv && oi < bi)) { bv = ov; bi = oi; }
        }
        bad |= bi == NEXP;
        if (bi < NEXP && (bi & 31) == lane) taken |= 1u << (bi >> 5);
        if (k == 0) top0 = bv;
        const float ek = __expf(bv - top0);
        z += ek;
        if (lane == k) {
            wk = ek;
            topi[t * TOPK + k] = bi;
        }
    }
    if (bad) {
        if (lane == 0) router_bad_row(err, bad_row, 2u, layer, t);
        if (lane < TOPK) {
            topi[t * TOPK + lane] = lane;
            topw[t * TOPK + lane] = 0.f;
        }
    } else if (lane < TOPK) topw[t * TOPK + lane] = wk / z;
}
}  // namespace
}  // namespace fnx
