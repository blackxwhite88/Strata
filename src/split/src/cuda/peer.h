// CUDA peer access between the cards and start probe (modelled on hip/peer.h and test_peer_reduction.cu).
// Enables direct NVLink/peer stores and bounded flag handshakes with fallback to host exchange.
#pragma once

#include <cuda_runtime.h>

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "../hip/peer_policy.hpp"

namespace fnx {

namespace peer_detail {
__global__ void k_fill(unsigned* p, size_t n, unsigned seed) {
    for (size_t e = blockIdx.x * (size_t) blockDim.x + threadIdx.x; e < n; e += (size_t) gridDim.x * blockDim.x)
        p[e] = seed ^ (unsigned) (e * 2654435761u);
}

__global__ void k_cmp(const unsigned* p, size_t n, unsigned seed, unsigned* bad) {
    unsigned b = 0;
    for (size_t e = blockIdx.x * (size_t) blockDim.x + threadIdx.x; e < n; e += (size_t) gridDim.x * blockDim.x)
        b += p[e] != (seed ^ (unsigned) (e * 2654435761u));
    if (b) atomicAdd(bad, b);
}

// flag ping-pong over peer memory with bounded timeout (clock64)
__global__ void k_ping(volatile unsigned* mine, volatile unsigned* theirs, int trips, int first, unsigned* ok) {
    if (threadIdx.x != 0) return;
    const long long limit = 100000000LL;  // ~100 ms limit
    for (int i = 1; i <= trips; ++i) {
        if (first) { *theirs = (unsigned) i; __threadfence_system(); }
        const long long t0 = clock64();
        while (*mine < (unsigned) i) {
            if ((long long)(clock64() - t0) > limit) return;
        }
        if (!first) { *theirs = (unsigned) i; __threadfence_system(); }
    }
    *ok = 1;
}
}  // namespace peer_detail

#define FNX_PEER_CK(x, what)                                                                                  \
    do {                                                                                                      \
        const cudaError_t e_ = (x);                                                                           \
        if (e_ != cudaSuccess) {                                                                              \
            cudaGetLastError();                                                                               \
            why = std::string(what) + ": " + cudaGetErrorString(e_);                                          \
            return false;                                                                                     \
        }                                                                                                     \
    } while (0)

inline bool peer_enable_and_probe(const std::vector<int>& devs, std::string& why) {
    using namespace peer_detail;
    for (int a : devs) {
        for (int b : devs) {
            if (a == b) continue;
            int can = 0;
            if (cudaDeviceCanAccessPeer(&can, a, b) != cudaSuccess || !can) {
                why = "card " + std::to_string(a) + " cannot access card " + std::to_string(b);
                return false;
            }
        }
    }

    for (int a : devs) {
        FNX_PEER_CK(cudaSetDevice(a), "set device");
        for (int b : devs) {
            if (a == b) continue;
            const cudaError_t e = cudaDeviceEnablePeerAccess(b, 0);
            if (e != cudaSuccess && e != cudaErrorPeerAccessAlreadyEnabled) {
                cudaGetLastError();
                why = "enabling access from card " + std::to_string(a) + " to card " + std::to_string(b) + ": " + cudaGetErrorString(e);
                return false;
            }
        }
    }

    const size_t n = (size_t) 1 << 20;  // 4 MiB (1M words)
    double worst_rt = 0.0;

    for (size_t ia = 0; ia < devs.size(); ++ia) {
        for (size_t ib = 0; ib < devs.size(); ++ib) {
            if (ia == ib) continue;
            const int a = devs[ia], b = devs[ib];
            const std::string pair = "card " + std::to_string(a) + " -> card " + std::to_string(b);
            unsigned *buf = nullptr, *bad_a = nullptr, *bad_b = nullptr, *fa = nullptr, *fb = nullptr, *oka = nullptr, *okb = nullptr;
            const unsigned seed = 0x5eed0000u + (unsigned) (a * 16 + b);
            bool pass = true;
            std::string pwhy;

            auto cleanup = [&] {
                cudaSetDevice(b);
                if (buf) cudaFree(buf);
                if (bad_b) cudaFree(bad_b);
                if (fb) cudaFree(fb);
                if (okb) cudaFree(okb);
                cudaSetDevice(a);
                if (bad_a) cudaFree(bad_a);
                if (fa) cudaFree(fa);
                if (oka) cudaFree(oka);
            };

            do {
                unsigned h = 0;
                std::string& why_ = pwhy;
                auto fail = [&](const std::string& s) { pass = false; why_ = pair + ": " + s; };

                // Allocate on receiver
                if (cudaSetDevice(b) != cudaSuccess) { fail("set device"); break; }
                if (cudaMalloc((void**) &buf, n * 4) != cudaSuccess || cudaMemset(buf, 0, n * 4) != cudaSuccess ||
                    cudaMalloc((void**) &bad_b, 4) != cudaSuccess || cudaMemset(bad_b, 0, 4) != cudaSuccess ||
                    cudaMalloc((void**) &fb, 256) != cudaSuccess || cudaMemset(fb, 0, 256) != cudaSuccess ||
                    cudaMalloc((void**) &okb, 4) != cudaSuccess || cudaMemset(okb, 0, 4) != cudaSuccess) {
                    cudaGetLastError(); fail("allocation on receiving card"); break;
                }

                // Allocate on sender
                if (cudaSetDevice(a) != cudaSuccess) { fail("set device"); break; }
                if (cudaMalloc((void**) &bad_a, 4) != cudaSuccess || cudaMemset(bad_a, 0, 4) != cudaSuccess ||
                    cudaMalloc((void**) &fa, 256) != cudaSuccess || cudaMemset(fa, 0, 256) != cudaSuccess ||
                    cudaMalloc((void**) &oka, 4) != cudaSuccess || cudaMemset(oka, 0, 4) != cudaSuccess) {
                    cudaGetLastError(); fail("allocation on sending card"); break;
                }

                // 1. Sender stores into receiver's memory
                k_fill<<<64, 256>>>(buf, n, seed);
                if (cudaDeviceSynchronize() != cudaSuccess) {
                    cudaGetLastError(); fail("store kernel failed"); break;
                }

                // 2. Receiver compares locally
                if (cudaSetDevice(b) != cudaSuccess) { fail("set device"); break; }
                k_cmp<<<64, 256>>>(buf, n, seed, bad_b);
                if (cudaDeviceSynchronize() != cudaSuccess || cudaMemcpy(&h, bad_b, 4, cudaMemcpyDeviceToHost) != cudaSuccess) {
                    cudaGetLastError(); fail("compare kernel failed"); break;
                }
                if (h) {
                    fail(std::to_string(h) + " of " + std::to_string(n) + " words arrived wrong (#2666 data corruption)");
                    break;
                }

                // 3. Sender reads back remotely
                if (cudaSetDevice(a) != cudaSuccess) { fail("set device"); break; }
                k_cmp<<<64, 256>>>(buf, n, seed, bad_a);
                if (cudaDeviceSynchronize() != cudaSuccess || cudaMemcpy(&h, bad_a, 4, cudaMemcpyDeviceToHost) != cudaSuccess) {
                    cudaGetLastError(); fail("read-back kernel failed"); break;
                }
                if (h) {
                    fail(std::to_string(h) + " of " + std::to_string(n) + " words read back wrong");
                    break;
                }

                // 4. Flag round trips (bounded wait)
                const int trips = 200;
                cudaStream_t sa, sb;
                if (cudaSetDevice(a) != cudaSuccess || cudaStreamCreateWithFlags(&sa, cudaStreamNonBlocking) != cudaSuccess) {
                    fail("stream creation on card a"); break;
                }
                if (cudaSetDevice(b) != cudaSuccess || cudaStreamCreateWithFlags(&sb, cudaStreamNonBlocking) != cudaSuccess) {
                    cudaStreamDestroy(sa); fail("stream creation on card b"); break;
                }

                const auto t0 = std::chrono::steady_clock::now();
                cudaSetDevice(b); k_ping<<<1, 64, 0, sb>>>(fb, fa, trips, 0, okb);
                cudaSetDevice(a); k_ping<<<1, 64, 0, sa>>>(fa, fb, trips, 1, oka);
                cudaSetDevice(a); const cudaError_t ea = cudaStreamSynchronize(sa);
                cudaSetDevice(b); const cudaError_t eb = cudaStreamSynchronize(sb);
                const double us = std::chrono::duration<double, std::micro>(std::chrono::steady_clock::now() - t0).count() / trips;

                cudaSetDevice(a); cudaStreamDestroy(sa);
                cudaSetDevice(b); cudaStreamDestroy(sb);

                unsigned va = 0, vb = 0;
                cudaSetDevice(a); cudaMemcpy(&va, oka, 4, cudaMemcpyDeviceToHost);
                cudaSetDevice(b); cudaMemcpy(&vb, okb, 4, cudaMemcpyDeviceToHost);

                if (ea != cudaSuccess || eb != cudaSuccess || !va || !vb) {
                    cudaGetLastError(); fail("peer flag round trip did not complete"); break;
                }
                if (us > worst_rt) worst_rt = us;
            } while (false);

            cleanup();
            if (!pass) { why = pwhy; return false; }
        }
    }

    char buf[160];
    std::snprintf(buf, sizeof buf, "all %zu directed pairs: 4 MiB stored, compared in full on both sides, flag round trip at most %.1f us",
                  devs.size() * (devs.size() - 1), worst_rt);
    why = buf;
    return true;
}

#undef FNX_PEER_CK

}  // namespace fnx
