// Opt-in CUDA copy-engine service. Never called from a CUDA host callback.
#pragma once

#include <cuda_runtime.h>

#include <atomic>
#include <algorithm>
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
    bool prefetch_enabled() const { return false; }
    unsigned long long host_bytes() const { return 0; }
    static std::unique_ptr<ExpertCopy> create(const CardW& w, bool = false) {
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
    char* stage_ = nullptr;  // private staging, never a live cache slot
    size_t stage_stride_ = 0;
    int staged_[EXPERT_COPY_CAP] = {}, staged_n_ = 0, staged_layer_ = -1;
    unsigned long long prefetched_ = 0, wasted_ = 0, guessed_ = 0, used_ = 0;
    std::atomic<unsigned long long> host_bytes_{0};
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
        if (host_->prefetch) {
            if (!stage_ || staged_n_) throw std::runtime_error("prefetch staging is busy or disabled");
            for (int i = 0; i < n; ++i) {
                const int g = host_->expert[i];
                if (g < l * NEXP || g >= (l + 1) * NEXP) throw std::runtime_error("invalid prefetch expert");
                char* dst = stage_ + (size_t) i * stage_stride_;
                check(cudaMemcpyAsync(dst, gu_[g], gb, cudaMemcpyHostToDevice, stream_));
                check(cudaMemcpyAsync(dst + gb, dn_[g], db, cudaMemcpyHostToDevice, stream_));
                staged_[i] = g;
            }
            check(cudaStreamSynchronize(stream_));
            staged_n_ = n;
            staged_layer_ = l;
            prefetched_ += (unsigned long long) n * (gb + db);
            host_bytes_.fetch_add((unsigned long long) n * (gb + db), std::memory_order_relaxed);
            guessed_ += n;
            return;
        }
        int used = 0;
        for (int i = 0; i < n; ++i) {
            const int g = host_->expert[i];
            char* dst = host_->dst[i];
            const uintptr_t off = (uintptr_t) dst - (uintptr_t) ec.pool[p];
            if (g < l * NEXP || g >= (l + 1) * NEXP || off >= (size_t) ec.n[p] * ec.slot_bytes[p] || off % ec.slot_bytes[p])
                throw std::runtime_error("invalid expert copy destination");
            int hit = -1;
            if (staged_layer_ == l)
                for (int j = 0; j < staged_n_; ++j)
                    if (staged_[j] == g) { hit = j; break; }
            if (hit >= 0) {
                check(cudaMemcpyAsync(dst, stage_ + (size_t) hit * stage_stride_, gb + db, cudaMemcpyDeviceToDevice, stream_));
                ++used;
            } else {
                check(cudaMemcpyAsync(dst, gu_[g], gb, cudaMemcpyHostToDevice, stream_));
                check(cudaMemcpyAsync(dst + gb, dn_[g], db, cudaMemcpyHostToDevice, stream_));
            }
        }
        check(cudaStreamSynchronize(stream_));
        host_bytes_.fetch_add((unsigned long long) (n - used) * (gb + db), std::memory_order_relaxed);
        if (staged_n_) {
            const LayerW& L = w_.L[staged_layer_];
            wasted_ += (unsigned long long) (staged_n_ - used) * (L.gu_e_stride + L.down_e_stride);
            used_ += used;
        }
        staged_n_ = 0;
        staged_layer_ = -1;
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
        if (stage_) {
            // A completed decode window always consumes its last prediction.
            // Account for an interrupted window's outstanding staging as waste.
            if (staged_n_) {
                const LayerW& L = w_.L[staged_layer_];
                wasted_ += (unsigned long long) staged_n_ * (L.gu_e_stride + L.down_e_stride);
            }
            std::fprintf(stderr, "fnx: expert prefetch summary card %d: miss guesses %llu, used %llu, guess hit rate %.2f%%, "
                                 "bytes prefetched %llu, bytes wasted %llu\n", w_.dev, guessed_, used_,
                         guessed_ ? 100.0 * used_ / guessed_ : 0.0, prefetched_, wasted_);
            cudaFree(stage_);
        }
        if (stream_) cudaStreamDestroy(stream_);
        if (host_) cudaFreeHost(host_);
    }
    ExpertCopyRequest* mailbox() const { return device_; }
    bool prefetch_enabled() const { return stage_ != nullptr; }
    unsigned long long host_bytes() const { return host_bytes_.load(std::memory_order_relaxed); }
    static std::unique_ptr<ExpertCopy> create(const CardW& w, bool prefetch = false) {
        static_assert(EXPERT_COPY_CAP == MAXT * TOPK, "mailbox capacity");
        std::unique_ptr<ExpertCopy> c(new ExpertCopy(w));
        try {
            cudaDeviceProp prop{};
            check(cudaGetDeviceProperties(&prop, w.dev));
            if (!prop.canMapHostMemory || !prop.unifiedAddressing || prop.asyncEngineCount < 1 || prop.major < 6 ||
                prop.clockRate <= 0 || sizeof(void*) != 8)
                throw std::runtime_error("requires mapped UVA host memory and a CUDA copy engine (sm_60+)");
            host_aliases(w.ec_host_gu, w, false, c->gu_);
            host_aliases(w.ec_host_dn, w, true, c->dn_);
            if (prefetch) {
                for (const LayerW& L : w.L)
                    c->stage_stride_ = std::max(c->stage_stride_, L.gu_e_stride + L.down_e_stride);
                const cudaError_t e = cudaMalloc((void**) &c->stage_, EXPERT_COPY_CAP * c->stage_stride_);
                if (e != cudaSuccess) {
                    cudaGetLastError();
                    std::fprintf(stderr, "fnx: FNX_CACHE_PREFETCH: staging allocation failed (%s); demand copies only on card %d\n",
                                 cudaGetErrorString(e), w.dev);
                } else {
                    std::fprintf(stderr, "fnx: FNX_CACHE_PREFETCH: %zu bytes of private staging on card %d\n",
                                 EXPERT_COPY_CAP * c->stage_stride_, w.dev);
                }
            }
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
