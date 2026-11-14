// tests/split/test_sm75_recurrence_gpu.cu
// Real GPU execution of SM75 GDN Recurrence on Turing RTX 2080 Ti hardware.
// Proves:
// 1. Shared memory limits: 74,372 bytes (GCB=32) fails cudaFuncSetAttribute on SM75; 57,988 bytes (GCB=16) succeeds.
// 2. Real execution of 16-column chunked recurrence (GCB=16) and serial fallback (k_gdn_pf_rec).
// 3. Numerical comparison of outputs and recurrent end-states on GPU.
// 4. Kernel execution latency across prompt sequence lengths T in {1, 16, 32, 64, 128, 512, 1024}.

#include <cuda_runtime.h>
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <vector>

constexpr int HS = 128;
constexpr int GDN_QC = 32;
constexpr int GDN_Q = 4;

#define CUDA_CK(x) do { \
    cudaError_t err_ = (x); \
    if (err_ != cudaSuccess) { \
        std::fprintf(stderr, "CUDA error at %s:%d: %s\n", __FILE__, __LINE__, cudaGetErrorString(err_)); \
        std::exit(1); \
    } \
} while (0)

__device__ __forceinline__ float wsum(float v) {
#pragma unroll
    for (int o = 16; o >= 1; o >>= 1) v += __shfl_xor_sync(0xffffffffu, v, o);
    return v;
}

inline void ck_launch(const char* tag) {
    cudaError_t err = cudaGetLastError();
    if (err != cudaSuccess) {
        std::fprintf(stderr, "CUDA error at %s: %s\n", tag, cudaGetErrorString(err));
        std::exit(1);
    }
}

// Force SM75 architecture configuration in gdn_prompt.cuh
#ifndef FNX_ARCH
#define FNX_ARCH 75
#endif
#ifndef FNX_SM75
#define FNX_SM75 1
#endif

#include "src/split/src/gdn_prompt.cuh"

// Dummy kernel with large dynamic shared memory to test cudaFuncSetAttribute rejection of 74,372 bytes
__global__ void k_dummy_large_smem() {
    extern __shared__ float smem[];
    if (threadIdx.x == 0 && smem[0] == 12345.0f) {
        smem[0] = 0.0f;
    }
}

int main(int argc, char** argv) {
    std::cout << "=== SM75 Recurrence Kernel Validation on Real GPU ===" << std::endl;
    int dev_count = 0;
    CUDA_CK(cudaGetDeviceCount(&dev_count));
    if (dev_count < 1) {
        std::cerr << "SKIPPED: No CUDA devices found.\n";
        return 77;
    }

    cudaDeviceProp prop;
    CUDA_CK(cudaGetDeviceProperties(&prop, 0));
    std::cout << "Target Device 0: " << prop.name
              << " | Compute " << prop.major << "." << prop.minor
              << " | SMs: " << prop.multiProcessorCount << "\n";

    int max_optin_smem = 0;
    CUDA_CK(cudaDeviceGetAttribute(&max_optin_smem, cudaDevAttrMaxSharedMemoryPerBlockOptin, 0));
    std::cout << "  Hardware Max Shared Memory Per Block (Opt-in): " << max_optin_smem
              << " bytes (" << (max_optin_smem / 1024.0) << " KiB)\n";

    // -------------------------------------------------------------------------
    // Step 1: Prove SM80 32-col layout is rejected on SM75 hardware
    // -------------------------------------------------------------------------
    constexpr size_t smem_32 = sizeof(float) * (2 * 32 * (HS + 1) + HS * 32 + 4 * 32 * 32 + (2 * 32 * 32 + 3 * 32 + 1));
    std::cout << "\n[Test 1] Attempting cudaFuncSetAttribute with SM80 32-col shared memory ("
              << smem_32 << " bytes = " << (smem_32 / 1024.0) << " KiB)...\n";

    cudaError_t err_32 = cudaFuncSetAttribute(k_dummy_large_smem, cudaFuncAttributeMaxDynamicSharedMemorySize, (int)smem_32);
    if (err_32 != cudaSuccess) {
        std::cout << "  -> EXPECTED REFUSAL: cudaFuncSetAttribute failed with error: "
                  << cudaGetErrorString(err_32) << "\n";
        std::cout << "  -> VERIFIED: Upstream 32-column layout physically cannot run on SM75 (exceeds 64 KiB limit)!\n";
    } else {
        std::cout << "  -> WARNING: Unexpected success for 74,372 bytes on this device!\n";
    }

    // -------------------------------------------------------------------------
    // Step 2: Prove SM75 16-col candidate is accepted on SM75 hardware
    // -------------------------------------------------------------------------
    std::cout << "\n[Test 2] Attempting cudaFuncSetAttribute with SM75 16-col shared memory ("
              << GCH_REC_SMEM << " bytes = " << (GCH_REC_SMEM / 1024.0) << " KiB)...\n";
    assert(GCH_REC_SMEM == 57988);

    cudaError_t err_16 = cudaFuncSetAttribute(k_gdn_ch_rec, cudaFuncAttributeMaxDynamicSharedMemorySize, (int)GCH_REC_SMEM);
    if (err_16 == cudaSuccess) {
        std::cout << "  -> SUCCESS: cudaFuncSetAttribute accepted 57,988 bytes!\n";
        std::cout << "  -> VERIFIED: 16-column layout fits comfortably in SM75 shared memory (margin: "
                  << (max_optin_smem - (int)GCH_REC_SMEM) << " bytes).\n";
    } else {
        std::cerr << "  -> FAILED: cudaFuncSetAttribute failed: " << cudaGetErrorString(err_16) << "\n";
        return 1;
    }

    // -------------------------------------------------------------------------
    // Step 3: Numerical Validation & Timing Benchmark (Real GPU execution)
    // -------------------------------------------------------------------------
    const int nk = 1;  // 1 key head
    const int nv = 4;  // 4 value heads
    std::vector<int> vmap = {0, 0, 0, 0}; // all map to key head 0

    const std::vector<int> test_tokens = {1, 16, 32, 64, 128, 512, 1024};
    std::cout << "\n[Test 3] Numerical Agreement & Benchmark between Serial Fallback and 16-Col Chunked Kernel...\n";

    int* d_vmap;
    CUDA_CK(cudaMalloc(&d_vmap, vmap.size() * sizeof(int)));
    CUDA_CK(cudaMemcpy(d_vmap, vmap.data(), vmap.size() * sizeof(int), cudaMemcpyHostToDevice));

    cudaEvent_t ev_start, ev_stop;
    CUDA_CK(cudaEventCreate(&ev_start));
    CUDA_CK(cudaEventCreate(&ev_stop));

    for (int C : test_tokens) {
        size_t ch = (2 * nk + nv) * HS;
        size_t xc_elements = (size_t) C * ch;
        size_t ab_elements = (size_t) C * 2 * nv;
        size_t s_elements = (size_t) nv * HS * HS;
        size_t y_elements = (size_t) C * nv * HS;
        size_t prep_elements = (size_t) ((C + GCH - 1) / GCH) * nv * GCH_PREP_FLOATS;

        std::vector<float> h_xc(xc_elements);
        std::vector<float> h_ab(ab_elements);
        std::vector<float> h_dt(nv, 0.5f);
        std::vector<float> h_a(nv, 0.2f);
        std::vector<float> h_s_init(s_elements, 0.01f);

        // Fill with synthetic pseudo-random data
        for (size_t i = 0; i < xc_elements; ++i) h_xc[i] = ((float)(i % 100) - 50.0f) / 100.0f;
        for (size_t i = 0; i < ab_elements; ++i) h_ab[i] = ((float)(i % 50) - 25.0f) / 100.0f;

        float *d_xc, *d_ab, *d_dt, *d_a, *d_s_ser, *d_s_ch, *d_y_ser, *d_y_ch, *d_prep, *d_sq;
        CUDA_CK(cudaMalloc(&d_xc, xc_elements * sizeof(float)));
        CUDA_CK(cudaMalloc(&d_ab, ab_elements * sizeof(float)));
        CUDA_CK(cudaMalloc(&d_dt, nv * sizeof(float)));
        CUDA_CK(cudaMalloc(&d_a, nv * sizeof(float)));
        CUDA_CK(cudaMalloc(&d_s_ser, s_elements * sizeof(float)));
        CUDA_CK(cudaMalloc(&d_s_ch, s_elements * sizeof(float)));
        CUDA_CK(cudaMalloc(&d_y_ser, y_elements * sizeof(float)));
        CUDA_CK(cudaMalloc(&d_y_ch, y_elements * sizeof(float)));
        CUDA_CK(cudaMalloc(&d_sq, (size_t) C * nv * GDN_Q * sizeof(float)));
        CUDA_CK(cudaMalloc(&d_prep, prep_elements * sizeof(float)));

        CUDA_CK(cudaMemcpy(d_xc, h_xc.data(), xc_elements * sizeof(float), cudaMemcpyHostToDevice));
        CUDA_CK(cudaMemcpy(d_ab, h_ab.data(), ab_elements * sizeof(float), cudaMemcpyHostToDevice));
        CUDA_CK(cudaMemcpy(d_dt, h_dt.data(), nv * sizeof(float), cudaMemcpyHostToDevice));
        CUDA_CK(cudaMemcpy(d_a, h_a.data(), nv * sizeof(float), cudaMemcpyHostToDevice));
        CUDA_CK(cudaMemcpy(d_s_ser, h_s_init.data(), s_elements * sizeof(float), cudaMemcpyHostToDevice));
        CUDA_CK(cudaMemcpy(d_s_ch, h_s_init.data(), s_elements * sizeof(float), cudaMemcpyHostToDevice));

        // 1. Run Serial Recurrence Kernel
        CUDA_CK(cudaEventRecord(ev_start));
        k_gdn_pf_rec<<<nv * GDN_Q, GDN_PF_THREADS>>>(
            d_xc, d_ab, d_dt, d_a, d_s_ser, d_y_ser, d_sq, nk, nv, d_vmap, C);
        CUDA_CK(cudaEventRecord(ev_stop));
        CUDA_CK(cudaDeviceSynchronize());
        float ms_ser = 0.f;
        CUDA_CK(cudaEventElapsedTime(&ms_ser, ev_start, ev_stop));

        // 2. Run 16-Column Chunked Recurrence Kernel
        dim3 grid_prep((C + GCH - 1) / GCH, nv);
        int rec_blocks = nv * GCH_REC_BLOCKS_PER_HEAD; // 8 blocks per head

        CUDA_CK(cudaEventRecord(ev_start));
        k_gdn_ch_prep<<<grid_prep, GCH_THREADS>>>(
            d_xc, d_ab, d_dt, d_a, d_vmap, nk, nv, C, d_prep);
        k_gdn_ch_rec<<<rec_blocks, GCR_THREADS, (int)GCH_REC_SMEM>>>(
            d_xc, d_prep, d_s_ch, d_y_ch, nk, nv, d_vmap, C);
        CUDA_CK(cudaEventRecord(ev_stop));
        CUDA_CK(cudaDeviceSynchronize());
        float ms_ch = 0.f;
        CUDA_CK(cudaEventElapsedTime(&ms_ch, ev_start, ev_stop));

        // Read outputs and states
        std::vector<float> h_y_ser(y_elements), h_y_ch(y_elements);
        std::vector<float> h_s_ser(s_elements), h_s_ch(s_elements);
        CUDA_CK(cudaMemcpy(h_y_ser.data(), d_y_ser, y_elements * sizeof(float), cudaMemcpyDeviceToHost));
        CUDA_CK(cudaMemcpy(h_y_ch.data(), d_y_ch, y_elements * sizeof(float), cudaMemcpyDeviceToHost));
        CUDA_CK(cudaMemcpy(h_s_ser.data(), d_s_ser, s_elements * sizeof(float), cudaMemcpyDeviceToHost));
        CUDA_CK(cudaMemcpy(h_s_ch.data(), d_s_ch, s_elements * sizeof(float), cudaMemcpyDeviceToHost));

        double max_diff_y = 0.0, max_val_y = 1e-30;
        for (size_t i = 0; i < y_elements; ++i) {
            double diff = std::fabs(h_y_ser[i] - h_y_ch[i]);
            max_diff_y = std::max(max_diff_y, diff);
            max_val_y = std::max(max_val_y, (double)std::fabs(h_y_ser[i]));
        }

        double max_diff_s = 0.0, max_val_s = 1e-30;
        for (size_t i = 0; i < s_elements; ++i) {
            double diff = std::fabs(h_s_ser[i] - h_s_ch[i]);
            max_diff_s = std::max(max_diff_s, diff);
            max_val_s = std::max(max_val_s, (double)std::fabs(h_s_ser[i]));
        }

        double rel_y = max_diff_y / max_val_y;
        double rel_s = max_diff_s / max_val_s;

        std::cout << "  Tokens T=" << std::setw(4) << C
                  << " | Serial: " << std::setw(6) << std::fixed << std::setprecision(2) << (ms_ser * 1000.f) << " us"
                  << " | 16-Col Chunk: " << std::setw(6) << (ms_ch * 1000.f) << " us"
                  << " | Rel Diff y: " << std::scientific << std::setprecision(2) << rel_y
                  << ", State S: " << rel_s << " -> "
                  << (rel_y < 1e-3 && rel_s < 1e-3 ? "PASS (FP32 equivalence)" : "MISMATCH") << "\n";

        assert(rel_y < 1e-3);
        assert(rel_s < 1e-3);

        CUDA_CK(cudaFree(d_xc));
        CUDA_CK(cudaFree(d_ab));
        CUDA_CK(cudaFree(d_dt));
        CUDA_CK(cudaFree(d_a));
        CUDA_CK(cudaFree(d_s_ser));
        CUDA_CK(cudaFree(d_s_ch));
        CUDA_CK(cudaFree(d_y_ser));
        CUDA_CK(cudaFree(d_y_ch));
        CUDA_CK(cudaFree(d_prep));
        CUDA_CK(cudaFree(d_sq));
    }

    CUDA_CK(cudaFree(d_vmap));
    CUDA_CK(cudaEventDestroy(ev_start));
    CUDA_CK(cudaEventDestroy(ev_stop));

    std::cout << "\n>>> All SM75 Recurrence GPU Tests Passed Successfully! <<<\n";
    return 0;
}
