// Exercise the actual host worker with CPU memory and fake CUDA calls.
#include "expert_copy.hpp"
#include <cassert>
#include <climits>

using namespace fnx;

static void complete(ExpertCopyRequest* q) {
    const auto until = std::chrono::steady_clock::now() + std::chrono::seconds(2);
    const unsigned seq = copy_request_load(&q->issued) + 1;
    copy_request_store(&q->issued, seq);
    while (copy_request_load(&q->done) != seq) {
        assert(std::chrono::steady_clock::now() < until);
        std::this_thread::yield();
    }
}

int main() {
    CardW w{};
    w.dev = 0;
    w.L.resize(NL);
    std::vector<char> gu((size_t) NL * NEXP * 16), dn(gu.size());
    std::vector<char> pool(4 * 32, 0);
    w.ec.pool[0] = pool.data();
    w.ec.n[0] = 4;
    w.ec.dn_off[0] = 16;
    w.ec.slot_bytes[0] = 32;
    for (int l = 0; l < NL; ++l) {
        w.L[l].gu_e_stride = w.L[l].down_e_stride = 16;
        for (int e = 0; e < NEXP; ++e) {
            const int g = l * NEXP + e;
            std::memset(gu.data() + (size_t) g * 16, g % 113 + 1, 16);
            std::memset(dn.data() + (size_t) g * 16, g % 97 + 1, 16);
            w.ec_host_gu.push_back(gu.data() + (size_t) g * 16);
            w.ec_host_dn.push_back(dn.data() + (size_t) g * 16);
        }
    }
    fake_pinned = false;
    assert(!ExpertCopy::create(w));  // pageable memory must fall back before any graph runs
    fake_pinned = true;
    auto service = ExpertCopy::create(w);
    assert(service);
    ExpertCopyRequest* q = service->mailbox();
    // Repeat requests and evict/reuse exactly the same destination. Check both
    // matrices after the completion flag; this also exercises sequence wrap.
    copy_request_store(&q->issued, UINT_MAX - 1);
    copy_request_store(&q->done, UINT_MAX - 1);
    for (int round = 0; round < 100; ++round) {
        q->layer = round % NL;
        q->count = round % 5;
        for (int i = 0; i < q->count; ++i) {
            q->expert[i] = q->layer * NEXP + round + i;
            q->dst[i] = pool.data() + i * 32;
        }
        complete(q);
        assert(!q->status);
        for (int i = 0; i < q->count; ++i) {
            assert(!std::memcmp(q->dst[i], w.ec_host_gu[q->expert[i]], 16));
            assert(!std::memcmp(q->dst[i] + 16, w.ec_host_dn[q->expert[i]], 16));
        }
    }
    {
        int slots[6] = {-1, 2, -1, -1, 0, -1}, out[EXPERT_COPY_CAP] = {};
        const int guesses[] = {0, 0, 1, -1, 2, 6, 5, 4, 2};
        const int n = copy_missing_guesses(guesses, 9, NEXP, 6, slots, out);
        assert(n == 3 && out[0] == NEXP && out[1] == NEXP + 2 && out[2] == NEXP + 5);
        auto prefetch = ExpertCopy::create(w, true);
        assert(prefetch && prefetch->prefetch_enabled());
        auto* p = prefetch->mailbox();
        p->layer = 1;
        p->prefetch = 1;
        p->count = 3;
        std::copy(out, out + n, p->expert);
        const auto hb = fake_host_bytes.load(), db = fake_device_bytes.load();
        complete(p);  // all three guesses staged; no live slot touched
        assert(fake_host_bytes.load() - hb == 96);
        assert(prefetch->host_bytes() == 96);
        p->prefetch = 0;
        p->count = 3;
        p->expert[0] = NEXP + 2;
        p->expert[1] = NEXP + 3;  // not predicted: demand H2D
        p->expert[2] = NEXP + 5;
        for (int i = 0; i < 3; ++i) p->dst[i] = pool.data() + i * 32;
        complete(p);
        assert(!p->status);
        assert(fake_host_bytes.load() - hb == 128);
        assert(fake_device_bytes.load() - db == 64);
        assert(prefetch->host_bytes() == 128);  // staging D2D must not count as host traffic
        for (int i = 0; i < 3; ++i) {
            assert(!std::memcmp(p->dst[i], w.ec_host_gu[p->expert[i]], 16));
            assert(!std::memcmp(p->dst[i] + 16, w.ec_host_dn[p->expert[i]], 16));
        }
        // Empty predictions and empty demand lists still handshake and release
        // staging for the following layer/window.
        p->prefetch = 1;
        p->count = 0;
        complete(p);
        p->prefetch = 0;
        complete(p);
        assert(!p->status);
    } // summary: 3 miss guesses, 2 used, 96 bytes prefetched, 32 wasted
    q->layer = 0;
    q->count = 1;
    q->expert[0] = 0;
    q->dst[0] = pool.data() + 1;
    complete(q);
    assert(q->status);  // invalid slot alignment fails closed
    q->dst[0] = pool.data();
    fake_fail_copy = 1;
    complete(q);
    assert(q->status);  // runtime copy failures are never reported as completion success
}
