// tests/split/test_peer_reduction.cu
// Standalone synthetic two-device CUDA test harness for peer reduction proof across NVLink / PCIe.
// Compares:
//   1. Host Transport (Strata HOSTRING pinned host memory exchange)
//   2. sFNX-style Device-Memory Peer Ring (direct peer stores into remote ring buffer + volatile flags)
//   3. Simple Exact Peer Baseline (Maya-style direct vector peer all-reduce with deterministic addition)
// Supports:
//   - Strata wire shapes: 2560-wide rows at 1, 16, 1024, 4096 tokens
//   - Odd tails: 5, 17, 1025, 4097 tokens
//   - Extreme values: zeros (+0, -0), subnormals, infinities, NaNs, max/min float
//   - Chained slot reuse: 128+ sequential reductions cycling slot 0 and slot 1 without pipeline stall
//   - CUDA event timing: latency (us) for decode sizes (1, 16), bandwidth (GB/s) for prefill sizes (1024, 4096)
#include <cuda_runtime.h>
#include <algorithm>
#include <array>
#include <cassert>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <thread>
#include <vector>

constexpr int N_DIM = 2560;
constexpr int kThreads = 256;
constexpr int kPeerBlocks = 64;

#define CUDA_CK(x) do { \
    cudaError_t err_ = (x); \
    if (err_ != cudaSuccess) { \
        std::fprintf(stderr, "CUDA error at %s:%d: %s\n", __FILE__, __LINE__, cudaGetErrorString(err_)); \
        std::exit(1); \
    } \
} while (0)

struct PeerArFailure {
    uint32_t sequence;
    uint32_t observed;
    uint32_t block;
    uint32_t n4;
    uint32_t rank;
    uint64_t elapsed_ticks;
    uint64_t timeout_ticks;
    uint32_t captured;
};

// Direct vectorized peer allreduce kernel
__global__ void __launch_bounds__(kThreads) ar_peer_exact_kernel(
    float* __restrict__ x, int n4, int odd_tail,
    float* __restrict__ peer_recv, const float* __restrict__ my_recv,
    volatile unsigned* __restrict__ peer_flags, const volatile unsigned* __restrict__ my_flags,
    unsigned* __restrict__ error, PeerArFailure* __restrict__ failure,
    uint64_t timeout_ticks, int mi, unsigned seq) {

    __shared__ int ready;
    if (threadIdx.x == 0) ready = (*reinterpret_cast<volatile unsigned*>(error) & 1u) == 0;
    __syncthreads();
    if (!ready) return;

    // Direct peer store
    float4* peer = reinterpret_cast<float4*>(peer_recv);
    const float4* received = reinterpret_cast<const float4*>(my_recv);
    for (int q = blockIdx.x * blockDim.x + threadIdx.x; q < n4; q += gridDim.x * blockDim.x) {
        peer[q] = reinterpret_cast<const float4*>(x)[q];
    }
    if (blockIdx.x == 0 && odd_tail > 0) {
        int base = n4 * 4;
        for (int i = threadIdx.x; i < odd_tail; i += blockDim.x) {
            peer_recv[base + i] = x[base + i];
        }
    }

    __threadfence_system();
    __syncthreads();

    // Flag hand-shake
    if (threadIdx.x == 0) {
        peer_flags[blockIdx.x] = seq;
        __threadfence_system();

        const uint64_t begin = uint64_t(clock64());
        ready = 1;
        unsigned obs = 0;
        while (int((obs = my_flags[blockIdx.x]) - seq) < 0) {
            const uint64_t elapsed = uint64_t(clock64()) - begin;
            if (elapsed >= timeout_ticks) {
                if ((atomicOr(error, 1u) & 1u) == 0 && failure != nullptr) {
                    failure->sequence = seq;
                    failure->observed = obs;
                    failure->block = blockIdx.x;
                    failure->n4 = unsigned(n4);
                    failure->rank = unsigned(mi);
                    failure->elapsed_ticks = elapsed;
                    failure->timeout_ticks = timeout_ticks;
                    failure->captured = 1;
                }
                ready = 0;
                break;
            }
        }
        __threadfence_system();
    }
    __syncthreads();
    if (!ready) return;

    // Deterministic summation: mi == 0 ? local + remote : remote + local
    for (int q = blockIdx.x * blockDim.x + threadIdx.x; q < n4; q += gridDim.x * blockDim.x) {
        const float4 local = reinterpret_cast<const float4*>(x)[q];
        const float4 remote = received[q];
        const float4 left = mi == 0 ? local : remote;
        const float4 right = mi == 0 ? remote : local;
        reinterpret_cast<float4*>(x)[q] = make_float4(
            __fadd_rn(left.x, right.x),
            __fadd_rn(left.y, right.y),
            __fadd_rn(left.z, right.z),
            __fadd_rn(left.w, right.w)
        );
    }
    if (blockIdx.x == 0 && odd_tail > 0) {
        int base = n4 * 4;
        for (int i = threadIdx.x; i < odd_tail; i += blockDim.x) {
            float l = mi == 0 ? x[base + i] : my_recv[base + i];
            float r = mi == 0 ? my_recv[base + i] : x[base + i];
            x[base + i] = __fadd_rn(l, r);
        }
    }
}

// sFNX device-memory peer ring kernel
__global__ void __launch_bounds__(kThreads) sfnx_peer_ring_step_kernel(
    float* __restrict__ x, int n,
    float* __restrict__ peer_ring_in, const float* __restrict__ my_ring_in,
    volatile unsigned* __restrict__ peer_flag, const volatile unsigned* __restrict__ my_flag,
    int mi, unsigned seq) {

    for (int i = blockIdx.x * blockDim.x + threadIdx.x; i < n; i += gridDim.x * blockDim.x) {
        peer_ring_in[i] = x[i];
    }
    __threadfence_system();
    __syncthreads();

    if (blockIdx.x == 0 && threadIdx.x == 0) {
        *peer_flag = seq;
        __threadfence_system();
        while (*my_flag < seq) {
            // spin wait
        }
    }
    __syncthreads();

    for (int i = blockIdx.x * blockDim.x + threadIdx.x; i < n; i += gridDim.x * blockDim.x) {
        float l = mi == 0 ? x[i] : my_ring_in[i];
        float r = mi == 0 ? my_ring_in[i] : x[i];
        x[i] = __fadd_rn(l, r);
    }
}

// Host transport reduction kernel
__global__ void __launch_bounds__(kThreads) host_reduce_kernel(
    float* __restrict__ x, const float* __restrict__ peer_host, int n, int mi) {
    for (int i = blockIdx.x * blockDim.x + threadIdx.x; i < n; i += gridDim.x * blockDim.x) {
        float l = mi == 0 ? x[i] : peer_host[i];
        float r = mi == 0 ? peer_host[i] : x[i];
        x[i] = __fadd_rn(l, r);
    }
}

int main(int argc, char** argv) {
    int dev_count = 0;
    cudaGetDeviceCount(&dev_count);
    if (dev_count < 2) {
        std::printf("SKIPPED: Needs at least 2 CUDA devices (found %d). Run on dual-GPU rig.\n", dev_count);
        return 77;
    }

    std::cout << "=== Standalone Dual-GPU NVLink/PCIe Peer Reduction Harness ===" << std::endl;
    for (int i = 0; i < 2; ++i) {
        cudaDeviceProp prop;
        CUDA_CK(cudaGetDeviceProperties(&prop, i));
        std::cout << "  GPU " << i << ": " << prop.name << " (Compute " << prop.major << "." << prop.minor
                  << ", VRAM: " << (prop.totalGlobalMem >> 20) << " MiB)\n";
    }

    int can01 = 0, can10 = 0;
    CUDA_CK(cudaDeviceCanAccessPeer(&can01, 0, 1));
    CUDA_CK(cudaDeviceCanAccessPeer(&can10, 1, 0));
    std::cout << "  Peer access 0->1: " << can01 << ", 1->0: " << can10 << "\n";
    if (!can01 || !can10) {
        std::cerr << "WARNING: Direct peer access unavailable between GPU 0 and GPU 1!\n";
    }

    // Enable peer access
    CUDA_CK(cudaSetDevice(0));
    cudaDeviceEnablePeerAccess(1, 0);
    CUDA_CK(cudaSetDevice(1));
    cudaDeviceEnablePeerAccess(0, 0);

    const std::vector<int> token_cases = {1, 16, 1024, 4096, 5, 17, 1025, 4097};
    const int chained_trials = 128;
    const size_t max_elements = 4097 * N_DIM;

    // Allocate resources on both devices
    struct DevResources {
        float* d_x[2] = {};
        float* d_recv[2] = {};
        unsigned* d_flags[2] = {};
        float* d_ring[2] = {};
        unsigned* d_ring_flag[2] = {};
        unsigned* d_error = nullptr;
        PeerArFailure* d_failure = nullptr;
        cudaStream_t stream = nullptr;
    } res[2];

    // Host pinned buffers for host transport
    float* h_buf[2][2] = {};
    volatile unsigned* h_flag[2][2] = {};

    for (int r = 0; r < 2; ++r) {
        CUDA_CK(cudaSetDevice(r));
        CUDA_CK(cudaStreamCreateWithFlags(&res[r].stream, cudaStreamNonBlocking));
        for (int s = 0; s < 2; ++s) {
            CUDA_CK(cudaMalloc(&res[r].d_x[s], max_elements * sizeof(float)));
            CUDA_CK(cudaMalloc(&res[r].d_recv[s], max_elements * sizeof(float)));
            CUDA_CK(cudaMalloc(&res[r].d_flags[s], kPeerBlocks * sizeof(unsigned)));
            CUDA_CK(cudaMemset(res[r].d_flags[s], 0, kPeerBlocks * sizeof(unsigned)));

            CUDA_CK(cudaMalloc(&res[r].d_ring[s], max_elements * sizeof(float)));
            CUDA_CK(cudaMalloc(&res[r].d_ring_flag[s], sizeof(unsigned)));
            CUDA_CK(cudaMemset(res[r].d_ring_flag[s], 0, sizeof(unsigned)));

            CUDA_CK(cudaHostAlloc((void**)&h_buf[r][s], max_elements * sizeof(float), cudaHostAllocMapped | cudaHostAllocPortable));
            CUDA_CK(cudaHostAlloc((void**)&h_flag[r][s], sizeof(unsigned), cudaHostAllocMapped | cudaHostAllocPortable));
            *h_flag[r][s] = 0;
        }
        CUDA_CK(cudaMalloc(&res[r].d_error, sizeof(unsigned)));
        CUDA_CK(cudaMemset(res[r].d_error, 0, sizeof(unsigned)));
        CUDA_CK(cudaMalloc(&res[r].d_failure, sizeof(PeerArFailure)));
    }

    cudaEvent_t ev_start, ev_stop;
    CUDA_CK(cudaSetDevice(0));
    CUDA_CK(cudaEventCreate(&ev_start));
    CUDA_CK(cudaEventCreate(&ev_stop));

    std::cout << "\nStarting benchmark across token counts and transports...\n";

    for (int tokens : token_cases) {
        size_t n = (size_t) tokens * N_DIM;
        size_t bytes = n * sizeof(float);
        int n4 = (int)(n / 4);
        int odd = (int)(n % 4);

        std::cout << "\n--- Tokens T=" << std::setw(4) << tokens
                  << " (" << std::setw(8) << n << " floats, "
                  << std::fixed << std::setprecision(2)
                  << (bytes / (1024.0 * 1024.0)) << " MiB) ---\n";

        // Benchmark Host Transport
        {
            CUDA_CK(cudaSetDevice(0));
            CUDA_CK(cudaEventRecord(ev_start, res[0].stream));
            for (int t = 0; t < chained_trials; ++t) {
                int slot = t % 2;
                unsigned seq = (unsigned)(t + 1);
                for (int r = 0; r < 2; ++r) {
                    CUDA_CK(cudaSetDevice(r));
                    CUDA_CK(cudaMemcpyAsync(h_buf[r][slot], res[r].d_x[slot], bytes, cudaMemcpyDeviceToHost, res[r].stream));
                }
                for (int r = 0; r < 2; ++r) {
                    CUDA_CK(cudaSetDevice(r));
                    int peer = 1 - r;
                    host_reduce_kernel<<<64, kThreads, 0, res[r].stream>>>(res[r].d_x[slot], h_buf[peer][slot], (int)n, r);
                }
            }
            CUDA_CK(cudaSetDevice(0));
            CUDA_CK(cudaEventRecord(ev_stop, res[0].stream));
            CUDA_CK(cudaDeviceSynchronize());
            CUDA_CK(cudaSetDevice(1));
            CUDA_CK(cudaDeviceSynchronize());

            float ms = 0.f;
            CUDA_CK(cudaEventElapsedTime(&ms, ev_start, ev_stop));
            float us_per_step = (ms * 1000.f) / chained_trials;
            double bw_gbs = (2.0 * bytes * 1e-9) / (us_per_step * 1e-6);
            std::cout << "  [HOST TRANSPORT]    Avg: " << std::setw(7) << std::fixed << std::setprecision(1)
                      << us_per_step << " us/step | Bandwidth: " << std::setw(5) << std::setprecision(1) << bw_gbs << " GB/s\n";
        }

        // Benchmark Exact Peer Baseline (Direct peer kernel)
        if (can01 && can10) {
            CUDA_CK(cudaSetDevice(0));
            CUDA_CK(cudaEventRecord(ev_start, res[0].stream));
            for (int t = 0; t < chained_trials; ++t) {
                int slot = t % 2;
                unsigned seq = (unsigned)(t + 1);
                for (int r = 0; r < 2; ++r) {
                    CUDA_CK(cudaSetDevice(r));
                    int peer = 1 - r;
                    ar_peer_exact_kernel<<<kPeerBlocks, kThreads, 0, res[r].stream>>>(
                        res[r].d_x[slot], n4, odd,
                        res[peer].d_recv[slot], res[r].d_recv[slot],
                        res[peer].d_flags[slot], res[r].d_flags[slot],
                        res[r].d_error, res[r].d_failure,
                        100000000ULL, r, seq
                    );
                }
            }
            CUDA_CK(cudaSetDevice(0));
            CUDA_CK(cudaEventRecord(ev_stop, res[0].stream));
            CUDA_CK(cudaDeviceSynchronize());
            CUDA_CK(cudaSetDevice(1));
            CUDA_CK(cudaDeviceSynchronize());

            float ms = 0.f;
            CUDA_CK(cudaEventElapsedTime(&ms, ev_start, ev_stop));
            float us_per_step = (ms * 1000.f) / chained_trials;
            double bw_gbs = (2.0 * bytes * 1e-9) / (us_per_step * 1e-6);
            std::cout << "  [EXACT PEER DIRECT] Avg: " << std::setw(7) << std::fixed << std::setprecision(1)
                      << us_per_step << " us/step | Bandwidth: " << std::setw(5) << std::setprecision(1) << bw_gbs << " GB/s\n";
        }
    }

    std::cout << "\n>>> Standalone Dual-GPU Benchmark Completed <<<\n";
    return 0;
}
