#include "read_interleave.hpp"
#include <cassert>
#include <cstdlib>

using namespace fnx;
int main() {
    unsetenv("FNX_READ_INTERLEAVE");
    setenv("FNX_READ_CHUNK_ROWS", "bad", 1);
    assert(!ReadInterleave::from_env().enabled); // unused knobs do not change defaults
    setenv("FNX_READ_INTERLEAVE", "1", 1);
    bool rejected = false;
    try { ReadInterleave::from_env(); } catch (const std::runtime_error&) { rejected = true; }
    assert(rejected);
    unsetenv("FNX_READ_CHUNK_ROWS");
    const auto p = ReadInterleave::from_env();
    assert(p.enabled && p.chunk_rows == 2048 && p.tokens == 8 && p.windows == 8);
    assert(prefill_slice_rows(8192, 0) == 8192);
    assert(prefill_slice_rows(8192, 2048) == 2048);
    assert(prefill_slice_rows(1024, 2048) == 1024);
    setenv("FNX_READ_DECODE_WINDOWS", "7", 1);
    rejected = false;
    try { ReadInterleave::from_env(); } catch (const std::runtime_error&) { rejected = true; }
    assert(rejected);
    unsetenv("FNX_READ_DECODE_WINDOWS");
    {
        std::vector<int> counts{10, 20, 0};
        std::vector<bool> active{true, true, false};
        ReadDecodeBudget b(p, counts, active);
        while (b.next(counts, active)) {
            counts[0] += 4;  // speculative lane accepts four
            ++counts[1];    // greedy lane must also reach its target
        }
        assert(b.windows() == 8 && b.met(counts, active));
    }
    {
        std::vector<int> counts{0};
        std::vector<bool> active{true};
        ReadDecodeBudget b(p, counts, active);
        while (b.next(counts, active)) counts[0] += 4;
        assert(b.windows() == 2); // stop promptly after reaching the token target
    }
    {
        ReadDecodeBudget b(p, {0}, {true});
        while (b.next({0}, {true})) {} // paused/page-starved lane cannot advance
        assert(b.windows() == 8 && !b.met({0}, {true}));
        assert(b.met({0}, {false})); // EOS/cancellation removes the lane's target
    }
    {
        ReadDecodeBudget b(p, {0}, {false});
        assert(!b.next({0}, {false})); // no decoding lane: no decode work
    }
}
