// One card, no model file. Build target split_router_guard_test, then run it (also under compute-sanitizer).
// Exercise the actual decode router/job builder and the prompt top-10 kernel with corrupt rows among finite rows.
#include "kernels.hpp"
#include "router_topk.cuh"

#include <cmath>
#include <cstdio>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <vector>

using namespace fnx;

namespace {
void check(bool ok, const char* message) { if (!ok) throw std::runtime_error(message); }
void ck(cudaError_t e) { if (e != cudaSuccess) throw std::runtime_error(cudaGetErrorString(e)); }
template <typename T> struct Device {
    T* p = nullptr;
    size_t n;
    explicit Device(size_t count) : n(count) { ck(cudaMalloc(&p, n * sizeof(T))); zero(); }
    ~Device() { cudaFree(p); }
    void zero() { ck(cudaMemset(p, 0, n * sizeof(T))); }
    void put(const std::vector<T>& v) { check(v.size() == n, "upload size"); ck(cudaMemcpy(p, v.data(), n * sizeof(T), cudaMemcpyHostToDevice)); }
    std::vector<T> get() const {
        std::vector<T> v(n);
        ck(cudaMemcpy(v.data(), p, n * sizeof(T), cudaMemcpyDeviceToHost));
        return v;
    }
};
void check_jobs(const std::vector<Job>& gu, const std::vector<Job>& dn, int nj, const std::vector<int>& picks) {
    check(nj > 0 && nj <= MAXT * TOPK, "job count out of range");
    std::vector<int> seen(MAXT * TOPK, 0), expert(NEXP, 0);
    for (int j = 0; j < nj; ++j) {
        const Job& g = gu[j];
        const Job& d = dn[j];
        check(g.w >= 0 && g.w < NEXP && d.w == g.w, "job expert out of range");
        check(++expert[g.w] == 1, "duplicate expert job");
        check(g.n > 0 && g.n <= MAXT && d.n == g.n, "job slots overflow");
        for (int s = 0; s < g.n; ++s) {
            const int pair = g.out[s];
            check(pair >= 0 && pair < MAXT * TOPK, "job pair out of range");
            check(g.y[s] == pair / TOPK && d.y[s] == pair && d.out[s] == pair, "job row mismatch");
            check(picks[pair] == g.w && ++seen[pair] == 1, "job pick mismatch");
        }
    }
    for (int count : seen) check(count == 1, "missing routed pair");
}
void run(bool prompt) {
    constexpr int layer = 7, bad_t = 8, P = MAXT * TOPK, L = NEXP + 1;
    Device<float> W((size_t) L * N), x((size_t) MAXT * N), logits((size_t) MAXT * L), weights(P);
    Device<int> picks(P), njobs(2);
    // Last element is a canary, including the job arrays' unused row slots.
    Device<Job> gu(P + 1), dn(P + 1);
    Device<unsigned> err(1);
    Device<RouterBadRow> first(1);
    std::vector<float> hw(W.n, 0.f), hx(x.n, 0.f), hl(logits.n);
    for (int e = 0; e < L; ++e) hw[(size_t) e * N] = (float) (e % 37) * 0.01f;
    for (int t = 0; t < MAXT; ++t) {
        hx[(size_t) t * N] = 1.f + t * 0.01f;
        for (int e = 0; e < L; ++e) hl[(size_t) t * L + e] = (float) (e % 37) * (0.01f + t * 0.0001f);
    }
    W.put(hw);
    auto launch = [&] {
        if (prompt) k_pf_top10<<<2, 256>>>(logits.p, MAXT, picks.p, weights.p, err.p, first.p, layer);
        else router_route(W.p, x.p, logits.p, MAXT, picks.p, weights.p, gu.p, dn.p, njobs.p, err.p, first.p, nullptr,
                          nullptr, layer);
        ck(cudaGetLastError());
        ck(cudaDeviceSynchronize());
    };
    x.put(hx); logits.put(hl); launch();
    const auto good_i = picks.get();
    const auto good_w = weights.get();
    check(err.get()[0] == 0 && first.get()[0].path == 0, "finite baseline raised an error");
    for (int mode = 0; mode < 5; ++mode) {
        auto bx = hx, bl = hl;
        // One NaN row, two NaN rows (the duplicate-expert overflow case), all NaN rows,
        // an inf row, and a prompt row with only nine finite logits.
        const int count = mode == 1 ? 2 : mode == 2 ? MAXT : 1;
        const float value = mode == 3 ? std::numeric_limits<float>::infinity() : std::numeric_limits<float>::quiet_NaN();
        std::vector<bool> bad(MAXT, false);
        for (int q = 0; q < count; ++q) {
            const int t = (bad_t + q) % MAXT;
            bad[t] = true;
            bx[(size_t) t * N] = value;
            for (int e = 0; e < L; ++e) bl[(size_t) t * L + e] = value;
            if (mode == 4) for (int e = 0; e < TOPK - 1; ++e) bl[(size_t) t * L + e] = (float) e;
        }
        x.put(bx); logits.put(bl); err.zero(); first.zero();
        const Job canary = {-123, -456, {}, {}};
        std::vector<Job> init(P + 1, canary);
        gu.put(init); dn.put(init);
        launch();
        const auto pi = picks.get();
        const auto pw = weights.get();
        check(err.get()[0] == 32u, "missing router bit 32");
        const RouterBadRow record = first.get()[0];
        check(record.path == (prompt ? 2u : 1u) && record.layer == layer && record.row >= 0 && record.row < MAXT && bad[record.row],
              "incorrect first-bad-row record");
        for (int t = 0; t < MAXT; ++t) for (int k = 0; k < TOPK; ++k) {
            const int p = t * TOPK + k;
            check(pi[p] >= 0 && pi[p] < NEXP, "topi out of range");
            if (bad[t]) check(pi[p] == k && pw[p] == 0.f, "bad row must route once to experts 0..9 with zero weights");
            else check(pi[p] == good_i[p] && std::memcmp(&pw[p], &good_w[p], sizeof(float)) == 0, "finite row changed");
        }
        if (!prompt) {
            const auto gj = gu.get(), dj = dn.get();
            check_jobs(gj, dj, njobs.get()[0], pi);
            check(std::memcmp(&gj[P], &canary, sizeof(Job)) == 0 && std::memcmp(&dj[P], &canary, sizeof(Job)) == 0,
                  "job buffer canary overwritten");
        }
        launch(); // a later bad row must not replace the first record
        const RouterBadRow again = first.get()[0];
        check(std::memcmp(&record, &again, sizeof(record)) == 0, "first record overwritten");
    }
    std::printf("%s router: finite rows unchanged, corrupt rows bounded, first record retained\n", prompt ? "prompt" : "decode");
}
}  // namespace
int main() {
    try { run(false); run(true); }
    catch (const std::exception& e) { std::fprintf(stderr, "router_guard_test: %s\n", e.what()); return 1; }
    return 0;
}
