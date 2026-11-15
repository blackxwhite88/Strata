// Server-side prompt/decode fairness policy; CPU-only so the budget is testable.
#pragma once

#include <algorithm>
#include <stdexcept>
#include <utility>
#include <vector>
#include "env.hpp"

namespace fnx {
inline int prefill_slice_rows(int allocated, int slice) { return slice > 0 ? std::min(allocated, slice) : allocated; }

struct ReadInterleave {
    bool enabled = false;
    int chunk_rows = 2048, tokens = 8, windows = 8;
    static ReadInterleave from_env() {
        ReadInterleave p;
        p.enabled = env_flag("FNX_READ_INTERLEAVE");
        if (!p.enabled) return p;  // ignored knobs cannot alter the default path
        const long long rows = env_int("FNX_READ_CHUNK_ROWS", 2048);
        const long long tokens = env_int("FNX_READ_DECODE_TOKENS", 8);
        const long long windows = env_int("FNX_READ_DECODE_WINDOWS", 8);
        if (rows < 256 || rows > 8192 || rows % 256)
            throw std::runtime_error("FNX_READ_CHUNK_ROWS: use 256..8192, a multiple of 256");
        if (tokens < 1 || tokens > 256 || windows < tokens || windows > 256)
            throw std::runtime_error("FNX_READ_DECODE_TOKENS/WINDOWS: require 1 <= tokens <= windows <= 256");
        p.chunk_rows = (int) rows;
        p.tokens = (int) tokens;
        p.windows = (int) windows;
        return p;
    }
};

// Snapshot each lane's count before the prompt yields. Finished/cancelled lanes
// leave the target set. A lane parked for lack of pages remains eligible, but
// the window cap ends the attempt even if it cannot advance.
class ReadDecodeBudget {
    std::vector<int> start_;
    std::vector<bool> eligible_;
    int tokens_, cap_, used_ = 0;
public:
    ReadDecodeBudget(const ReadInterleave& p, std::vector<int> counts, std::vector<bool> eligible)
        : start_(std::move(counts)), eligible_(std::move(eligible)), tokens_(p.tokens), cap_(p.windows) {}
    bool met(const std::vector<int>& counts, const std::vector<bool>& active) const {
        for (size_t i = 0; i < start_.size(); ++i)
            if (eligible_[i] && active[i] && counts[i] - start_[i] < tokens_) return false;
        return true;
    }
    bool next(const std::vector<int>& counts, const std::vector<bool>& active) {
        if (used_ >= cap_ || met(counts, active)) return false;
        ++used_;
        return true;
    }
    int windows() const { return used_; }
};
}  // namespace fnx
