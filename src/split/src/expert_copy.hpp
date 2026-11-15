// Opt-in CUDA copy-engine service. Never called from a CUDA host callback.
#pragma once

#include <cuda_runtime.h>

#include <atomic>
#include <chrono>
#include <cstdio>
#include <memory>
#include <new>
#include <stdexcept>
#include <thread>
#include <vector>

#include "expert_copy_protocol.hpp"
#include "model.hpp"

namespace fnx {
#if FNX_HIP
class ExpertCopy {
public:
    ExpertCopyRequest* mailbox() const { return nullptr; }
    static std::unique_ptr<ExpertCopy> create(const CardW& w) {
        std::fprintf(stderr, "fnx: FNX_CACHE_COPY_ENGINE: CUDA only; using SM copies on card %d\n", w.dev);
        return nullptr;
    }
};
#else
class ExpertCopy {
    const CardW& w_;
    cudaStream_t stream_ = nullptr;
    ExpertCopyRequest* host_ = nullptr;
    ExpertCopyRequest* device_ = nullptr;
    std::vector<const char*> gu_, dn_;
    std::atomic<bool> stop_{false};
    std::thread worker_;

    static void check(cudaError_t e) {
        if (e != cudaSuccess) throw std::runtime_error(cudaGetErrorString(e));
    }
    // The model stores device aliases of mapped host allocations. DMA needs the
    // CPU aliases. Check both ends of each contiguous layer matrix allocation.
    static void host_aliases(const std::vector<const char*>& mapped, const CardW& w,
                             bool down, std::vector<const char*>& out) {
        if (mapped.size() != (size_t) NL * NEXP) throw std::runtime_error("missing expert host table");
        out.resize(mapped.size());
        for (int l = 0; l < NL; ++l) {
            const size_t base = (size_t) l * NEXP;
            const size_t stride = down ? w.L[l].down_e_stride : w.L[l].gu_e_stride;
            cudaPointerAttributes a{}, z{};
            if (!stride || !mapped[base]) throw std::runtime_error("empty expert host allocation");
            check(cudaPointerGetAttributes(&a, mapped[base]));
            check(cudaPointerGetAttributes(&z, mapped[base] + NEXP * stride - 1));
            if (a.type != cudaMemoryTypeHost || z.type != cudaMemoryTypeHost || !a.hostPointer || !z.hostPointer ||
                (const char*) z.hostPointer != (const char*) a.hostPointer + NEXP * stride - 1)
                throw std::runtime_error("experts are not contiguous pinned host memory");
            for (int e = 0; e < NEXP; ++e) {
                if (mapped[base + e] != mapped[base] + (size_t) e * stride)
                    throw std::runtime_error("non-contiguous expert host table");
                out[base + e] = (const char*) a.hostPointer + (size_t) e * stride;
            }
        }
    }
    void fill() {
        const int l = host_->layer, n = host_->count;
        if (l < 0 || l >= NL || n < 0 || n > EXPERT_COPY_CAP) throw std::runtime_error("invalid copy request");
        const ExpertCache& ec = w_.ec;
        const int p = ec.pool_of[l];
        const size_t gb = w_.L[l].gu_e_stride, db = w_.L[l].down_e_stride;
        if (gb != ec.dn_off[p] || gb + db != ec.slot_bytes[p]) throw std::runtime_error("expert pool size mismatch");
        for (int i = 0; i < n; ++i) {
            const int g = host_->expert[i];
            char* dst = host_->dst[i];
            const uintptr_t off = (uintptr_t) dst - (uintptr_t) ec.pool[p];
            if (g < l * NEXP || g >= (l + 1) * NEXP || off >= (size_t) ec.n[p] * ec.slot_bytes[p] || off % ec.slot_bytes[p])
                throw std::runtime_error("invalid expert copy destination");
            check(cudaMemcpyAsync(dst, gu_[g], gb, cudaMemcpyHostToDevice, stream_));
            check(cudaMemcpyAsync(dst + gb, dn_[g], db, cudaMemcpyHostToDevice, stream_));
        }
        check(cudaStreamSynchronize(stream_));
    }
    void run() noexcept {
        const cudaError_t set = cudaSetDevice(w_.dev);
        unsigned idle = 0;
        while (!stop_.load(std::memory_order_relaxed)) {
            const unsigned seq = copy_request_load(&host_->issued);
            if (seq == copy_request_load(&host_->done)) {
                if (++idle < 4096) std::this_thread::yield();
                else std::this_thread::sleep_for(std::chrono::microseconds(10));
                continue;
            }
            idle = 0;
            try {
                check(set);
                fill();
                host_->status = 0;
            } catch (const std::exception& e) {
                // Fail closed: never release a reader to a partly filled slot.
                cudaStreamSynchronize(stream_);
                host_->status = 1;
                std::fprintf(stderr, "fnx: expert copy failed on card %d: %s\n", w_.dev, e.what());
            }
            copy_request_store(&host_->done, seq);
        }
    }
    explicit ExpertCopy(const CardW& w) : w_(w) {}

public:
    ~ExpertCopy() {
        stop_.store(true, std::memory_order_relaxed);
        if (worker_.joinable()) worker_.join();
        if (stream_) cudaStreamDestroy(stream_);
        if (host_) cudaFreeHost(host_);
    }
    ExpertCopyRequest* mailbox() const { return device_; }
    static std::unique_ptr<ExpertCopy> create(const CardW& w) {
        static_assert(EXPERT_COPY_CAP == MAXT * TOPK, "mailbox capacity");
        std::unique_ptr<ExpertCopy> c(new ExpertCopy(w));
        try {
            cudaDeviceProp prop{};
            check(cudaGetDeviceProperties(&prop, w.dev));
            if (!prop.canMapHostMemory || !prop.unifiedAddressing || prop.asyncEngineCount < 1 || prop.major < 6 || sizeof(void*) != 8)
                throw std::runtime_error("requires mapped UVA host memory and a CUDA copy engine (sm_60+)");
            host_aliases(w.ec_host_gu, w, false, c->gu_);
            host_aliases(w.ec_host_dn, w, true, c->dn_);
            check(cudaStreamCreateWithFlags(&c->stream_, cudaStreamNonBlocking));
            check(cudaHostAlloc((void**) &c->host_, sizeof(ExpertCopyRequest), cudaHostAllocMapped | cudaHostAllocPortable));
            new (c->host_) ExpertCopyRequest();
            c->host_->timeout_ticks = (unsigned long long) prop.clockRate * 1000 * 30;
            check(cudaHostGetDevicePointer((void**) &c->device_, c->host_, 0));
            c->worker_ = std::thread([p = c.get()] { p->run(); });
            std::fprintf(stderr, "fnx: FNX_CACHE_COPY_ENGINE: copy stream enabled on card %d\n", w.dev);
            return c;
        } catch (const std::exception& e) {
            cudaGetLastError();
            std::fprintf(stderr, "fnx: FNX_CACHE_COPY_ENGINE: %s; using SM copies on card %d\n", e.what(), w.dev);
            return nullptr;
        }
    }
};
#endif
}  // namespace fnx
