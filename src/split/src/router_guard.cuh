// Shared by the decode and prompt routers. The host reads the record after stream completion.
#pragma once
#include "kernels.hpp"
#include <cmath>

namespace fnx {
__device__ __forceinline__ void router_bad_row(unsigned* err, RouterBadRow* first, unsigned path, int layer, int row) {
    atomicOr(err, 32u);
    if (atomicCAS(&first->path, 0u, path) == 0u) {
        first->layer = layer;
        first->row = row;
    }
}
}  // namespace fnx
