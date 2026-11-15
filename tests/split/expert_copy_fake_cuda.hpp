// CPU test double only. This does not validate CUDA ordering or graph execution.
#pragma once
#include <cstdlib>
#include <cstring>
#include <cstdint>

using cudaError_t = int;
using cudaStream_t = void*;
constexpr int cudaSuccess = 0, cudaMemoryTypeHost = 1;
constexpr int cudaMemcpyHostToDevice = 1, cudaMemcpyDeviceToDevice = 2;
constexpr int cudaStreamNonBlocking = 1, cudaHostAllocMapped = 1, cudaHostAllocPortable = 2;
struct cudaDeviceProp {
    int canMapHostMemory = 1, unifiedAddressing = 1, asyncEngineCount = 1, major = 7, clockRate = 1000000;
};
struct cudaPointerAttributes { int type = cudaMemoryTypeHost; void* hostPointer = nullptr; };
inline bool fake_pinned = true;
inline int fake_fail_copy = 0;
inline const char* cudaGetErrorString(int) { return "fake CUDA error"; }
inline int cudaGetLastError() { return 0; }
inline int cudaSetDevice(int) { return 0; }
inline int cudaGetDeviceProperties(cudaDeviceProp* p, int) { *p = {}; return 0; }
inline int cudaPointerGetAttributes(cudaPointerAttributes* a, const void* p) {
    a->type = fake_pinned ? cudaMemoryTypeHost : 0;
    a->hostPointer = const_cast<void*>(p);
    return 0;
}
inline int cudaStreamCreateWithFlags(cudaStream_t* s, int) { *s = reinterpret_cast<void*>(1); return 0; }
inline int cudaStreamDestroy(cudaStream_t) { return 0; }
inline int cudaStreamSynchronize(cudaStream_t) { return 0; }
inline int cudaHostAlloc(void** p, size_t n, int) { *p = std::aligned_alloc(64, (n + 63) / 64 * 64); return *p ? 0 : 1; }
inline int cudaFreeHost(void* p) { std::free(p); return 0; }
inline int cudaHostGetDevicePointer(void** d, void* h, int) { *d = h; return 0; }
inline int cudaMalloc(void** p, size_t n) { *p = std::malloc(n); return *p ? 0 : 1; }
inline int cudaFree(void* p) { std::free(p); return 0; }
inline int cudaMemcpyAsync(void* dst, const void* src, size_t n, int, cudaStream_t) {
    if (fake_fail_copy) return fake_fail_copy;
    std::memcpy(dst, src, n);
    return 0;
}
