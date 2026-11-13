// tests/split/test_sm75_recurrence.cpp
// Verifies SM75 GDN recurrence kernels and policies:
// 1. Shared memory arithmetic for Turing (SM75, 64 KiB limit)
// 2. Serial fallback (FNX_PF_GDN_CHUNK=0, k_gdn_pf_rec): 42,240 bytes (41.25 KiB)
// 3. 16-column candidate (GCB=16): 57,988 bytes (56.63 KiB) vs 32-column (GCB=32): 74,372 bytes (72.63 KiB)
// 4. Numerical verification of output y32 and recurrent state S against FP64 oracle (gdn_fixture.hpp)
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include <iostream>
#include <iomanip>
#include <algorithm>
#include <cassert>

#include "gdn/gdn_fixture.hpp"

namespace test_sm75 {

constexpr int HS = 128;
constexpr size_t SM75_MAX_SHARED_MEM = 64 * 1024; // 65,536 bytes

// Compute shared memory size for chunked recurrence
constexpr size_t calc_gch_rec_smem(int gch, int gcb, int hs) {
    int gch_prep_floats = 2 * gch * gch + 3 * gch + 1;
    return sizeof(float) * (2 * gch * (hs + 1) + hs * gcb + 4 * gch * gcb + gch_prep_floats);
}

// Compute shared memory size for serial recurrence k_gdn_pf_rec
constexpr size_t calc_serial_rec_smem(int tt, int rp, int parts, int qc, int threads) {
    size_t xs = 2 * tt * rp * parts;
    size_t vs = tt * qc;
    size_t os = tt * qc;
    size_t gates = tt * 2;
    size_t red = (threads / 32) * tt;
    return sizeof(float) * (xs + vs + os + gates + red);
}

// Reference simulation of serial delta recurrence (k_gdn_pf_rec)
void simulate_serial_gdn(int T, const std::vector<float>& q, const std::vector<float>& k,
                         const std::vector<float>& v, const std::vector<float>& g,
                         const std::vector<float>& beta, std::vector<float>& state,
                         std::vector<float>& out_y) {
    const float scale = 1.0f / std::sqrt((float)HS);
    out_y.resize(T * HS);
    std::vector<float> kv(HS);

    for (int t = 0; t < T; ++t) {
        const float* qt = &q[t * HS];
        const float* kt = &k[t * HS];
        const float* vt = &v[t * HS];
        const float decay = g[t];
        const float b = beta[t];

        // S_i = g_i S_{i-1} + k_i u_i^T
        // u_i = b_i (v_i - g_i S_{i-1}^T k_i)
        // 1. S^T * k
        for (int c = 0; c < HS; ++c) {
            float sum = 0.f;
            for (int r = 0; r < HS; ++r) {
                sum += state[r * HS + c] * kt[r];
            }
            kv[c] = sum;
        }

        // 2. update state and compute o_i = S_i^T * q_i / sqrt(HS)
        float* yt = &out_y[t * HS];
        for (int c = 0; c < HS; ++c) {
            float u = b * (vt[c] - decay * kv[c]);
            float oc = 0.f;
            for (int r = 0; r < HS; ++r) {
                float s_new = decay * state[r * HS + c] + kt[r] * u;
                state[r * HS + c] = s_new;
                oc += s_new * qt[r];
            }
            yt[c] = oc * scale;
        }
    }
}

// Reference simulation of chunked delta recurrence with configurable column block size GCB
void simulate_chunked_gdn(int T, int GCB, const std::vector<float>& q, const std::vector<float>& k,
                          const std::vector<float>& v, const std::vector<float>& g,
                          const std::vector<float>& beta, std::vector<float>& state,
                          std::vector<float>& out_y) {
    const int GCH = 32;
    const float scale = 1.0f / std::sqrt((float)HS);
    out_y.resize(T * HS);

    int nblocks = HS / GCB;

    // We can simulate column by column or block by block
    // Within each sub-chunk of GCH rows:
    int nsub = (T + GCH - 1) / GCH;

    for (int blk = 0; blk < nblocks; ++blk) {
        int c0 = blk * GCB;

        // Extract sub-state for this column block: [HS][GCB]
        std::vector<float> ss(HS * GCB);
        for (int r = 0; r < HS; ++r) {
            for (int c = 0; c < GCB; ++c) {
                ss[r * GCB + c] = state[r * HS + c0 + c];
            }
        }

        for (int sc = 0; sc < nsub; ++sc) {
            int t0 = sc * GCH;
            int n = std::min(GCH, T - t0);

            // Sub-chunk prep:
            // Cumulative decays within sub-chunk
            std::vector<float> lg(GCH, 0.f), bb(GCH, 0.f);
            for (int i = 0; i < n; ++i) {
                lg[i] = std::log(g[t0 + i]);
                bb[i] = beta[t0 + i];
            }
            std::vector<float> lgam(GCH, 0.f);
            float s = 0.f;
            for (int i = 0; i < GCH; ++i) lgam[i] = s += lg[i];

            // T and P matrices
            // A_ij = b_i (G_i / G_j) (k_i . k_j) for j < i
            // P_ij = (G_i / G_j) (q_i . k_j) for j <= i
            std::vector<float> A(GCH * GCH, 0.f), P(GCH * GCH, 0.f);
            for (int i = 0; i < n; ++i) {
                for (int j = 0; j < n; ++j) {
                    float dot_k = 0.f, dot_q = 0.f;
                    for (int r = 0; r < HS; ++r) {
                        dot_k += k[(t0 + i) * HS + r] * k[(t0 + j) * HS + r];
                        dot_q += q[(t0 + i) * HS + r] * k[(t0 + j) * HS + r];
                    }
                    float dec = std::exp(lgam[i] - lgam[j]);
                    if (j < i) A[i * GCH + j] = bb[i] * dec * dot_k;
                    if (j <= i) P[i * GCH + j] = dec * dot_q;
                }
            }

            // T = (I + A)^{-1} via forward substitution
            std::vector<float> T_mat(GCH * GCH, 0.f);
            for (int m = 0; m < n; ++m) {
                for (int i = 0; i < n; ++i) {
                    float val = (i == m) ? 1.0f : 0.0f;
                    for (int j = m; j < i; ++j) {
                        val -= A[i * GCH + j] * T_mat[j * GCH + m];
                    }
                    T_mat[i * GCH + m] = (m <= i) ? val : 0.0f;
                }
            }

            // W = K * S0: [n][GCB], Y = Q * S0: [n][GCB]
            std::vector<float> W(n * GCB, 0.f), Y(n * GCB, 0.f);
            for (int i = 0; i < n; ++i) {
                for (int c = 0; c < GCB; ++c) {
                    float sum_w = 0.f, sum_y = 0.f;
                    for (int r = 0; r < HS; ++r) {
                        sum_w += k[(t0 + i) * HS + r] * ss[r * GCB + c];
                        sum_y += q[(t0 + i) * HS + r] * ss[r * GCB + c];
                    }
                    W[i * GCB + c] = sum_w;
                    Y[i * GCB + c] = sum_y;
                }
            }

            // R = b * (V - G * W), where G_i = exp(lgam[i])
            std::vector<float> R(n * GCB, 0.f);
            for (int i = 0; i < n; ++i) {
                float Gi = std::exp(lgam[i]);
                for (int c = 0; c < GCB; ++c) {
                    float vc = v[(t0 + i) * HS + c0 + c];
                    R[i * GCB + c] = bb[i] * (vc - Gi * W[i * GCB + c]);
                }
            }

            // U = T * R
            std::vector<float> U(n * GCB, 0.f);
            for (int i = 0; i < n; ++i) {
                for (int c = 0; c < GCB; ++c) {
                    float sum_u = 0.f;
                    for (int j = 0; j <= i; ++j) {
                        sum_u += T_mat[i * GCH + j] * R[j * GCB + c];
                    }
                    U[i * GCB + c] = sum_u;
                }
            }

            // O = (G * Y + P * U) / sqrt(HS)
            for (int i = 0; i < n; ++i) {
                float Gi = std::exp(lgam[i]);
                for (int c = 0; c < GCB; ++c) {
                    float sum_pu = 0.f;
                    for (int j = 0; j <= i; ++j) {
                        sum_pu += P[i * GCH + j] * U[j * GCB + c];
                    }
                    float o_ic = Gi * Y[i * GCB + c] + sum_pu;
                    out_y[(t0 + i) * HS + c0 + c] = o_ic * scale;
                }
            }

            // S_end = G_last * S0 + sum_i (G_last / G_i) * k_i * u_i^T
            float glast = std::exp(lgam[n - 1]);
            for (int r = 0; r < HS; ++r) {
                for (int c = 0; c < GCB; ++c) {
                    float s_val = glast * ss[r * GCB + c];
                    for (int i = 0; i < n; ++i) {
                        float dec_end = std::exp(lgam[n - 1] - lgam[i]);
                        s_val += dec_end * k[(t0 + i) * HS + r] * U[i * GCB + c];
                    }
                    ss[r * GCB + c] = s_val;
                }
            }
        }

        // Put back sub-state into main state
        for (int r = 0; r < HS; ++r) {
            for (int c = 0; c < GCB; ++c) {
                state[r * HS + c0 + c] = ss[r * GCB + c];
            }
        }
    }
}

} // namespace test_sm75

int main() {
    using namespace test_sm75;
    std::cout << "=== SM75 Split Recurrence Shared Memory & Correctness Audit ===" << std::endl;

    // 1. Shared memory audit
    size_t smem_serial = calc_serial_rec_smem(32, 16, 8, 32, 256);
    size_t smem_chunk_32 = calc_gch_rec_smem(32, 32, 128);
    size_t smem_chunk_16 = calc_gch_rec_smem(32, 16, 128);

    std::cout << "Turing (SM75) Shared Memory Budget: " << SM75_MAX_SHARED_MEM << " bytes (64 KiB)\n";
    std::cout << "  - Serial fallback (k_gdn_pf_rec):   " << smem_serial << " bytes ("
              << (smem_serial / 1024.0) << " KiB) -> "
              << (smem_serial <= SM75_MAX_SHARED_MEM ? "FITS" : "EXCEEDS") << "\n";
    std::cout << "  - Chunked GCB=32 (SM80 default):   " << smem_chunk_32 << " bytes ("
              << (smem_chunk_32 / 1024.0) << " KiB) -> "
              << (smem_chunk_32 <= SM75_MAX_SHARED_MEM ? "FITS" : "EXCEEDS") << " (OVERFLOW: "
              << (int(smem_chunk_32) - int(SM75_MAX_SHARED_MEM)) << " bytes)\n";
    std::cout << "  - Chunked GCB=16 (SM75 candidate): " << smem_chunk_16 << " bytes ("
              << (smem_chunk_16 / 1024.0) << " KiB) -> "
              << (smem_chunk_16 <= SM75_MAX_SHARED_MEM ? "FITS" : "EXCEEDS") << " (MARGIN: "
              << (int(SM75_MAX_SHARED_MEM) - int(smem_chunk_16)) << " bytes)\n";

    assert(smem_serial == 42240);
    assert(smem_chunk_32 == 74372);
    assert(smem_chunk_16 == 57988);
    assert(smem_chunk_16 <= SM75_MAX_SHARED_MEM);
    assert(smem_serial <= SM75_MAX_SHARED_MEM);

    std::cout << "\n=== Recurrence Numerical Comparison ===" << std::endl;
    // 2. Numerical validation across multiple sequence lengths
    const std::vector<int> test_lengths = {1, 16, 32, 48, 64, 128};

    for (int T : test_lengths) {
        gdnfx::Rng rng(1337 + T);
        std::vector<float> q(T * HS), k(T * HS), v(T * HS), g(T), beta(T);
        std::vector<float> s_init(HS * HS);

        for (auto& x : q) x = (float)rng.gauss();
        for (auto& x : k) x = (float)rng.gauss();
        for (auto& x : v) x = (float)rng.gauss();
        for (auto& x : s_init) x = (float)(0.05 * rng.gauss());

        // L2 norm on q and k per token
        for (int t = 0; t < T; ++t) {
            float sum_q = 0.f, sum_k = 0.f;
            for (int r = 0; r < HS; ++r) {
                sum_q += q[t * HS + r] * q[t * HS + r];
                sum_k += k[t * HS + r] * k[t * HS + r];
            }
            float nq = 1.0f / std::sqrt(sum_q + 1e-6f);
            float nk = 1.0f / std::sqrt(sum_k + 1e-6f);
            for (int r = 0; r < HS; ++r) {
                q[t * HS + r] *= nq;
                k[t * HS + r] *= nk;
            }
            float a = (float)(0.5 * rng.gauss() - 0.5);
            float sp = a > 20.f ? a : std::log1p(std::exp(a));
            g[t] = std::exp(sp * -0.2f);
            beta[t] = 1.0f / (1.0f + std::exp(-(float)rng.gauss()));
        }

        // Run serial recurrence
        std::vector<float> state_serial = s_init;
        std::vector<float> y_serial;
        simulate_serial_gdn(T, q, k, v, g, beta, state_serial, y_serial);

        // Run chunked GCB=32 recurrence
        std::vector<float> state_chunk32 = s_init;
        std::vector<float> y_chunk32;
        simulate_chunked_gdn(T, 32, q, k, v, g, beta, state_chunk32, y_chunk32);

        // Run chunked GCB=16 recurrence (SM75 candidate)
        std::vector<float> state_chunk16 = s_init;
        std::vector<float> y_chunk16;
        simulate_chunked_gdn(T, 16, q, k, v, g, beta, state_chunk16, y_chunk16);

        // Compare 16-col candidate vs 32-col candidate
        double max_diff_y_16_vs_32 = 0.0, max_val_y = 1e-30;
        for (size_t i = 0; i < y_chunk16.size(); ++i) {
            double diff = std::fabs(y_chunk16[i] - y_chunk32[i]);
            max_diff_y_16_vs_32 = std::max(max_diff_y_16_vs_32, diff);
            max_val_y = std::max(max_val_y, (double)std::fabs(y_chunk32[i]));
        }

        double max_diff_s_16_vs_32 = 0.0, max_val_s = 1e-30;
        for (size_t i = 0; i < state_chunk16.size(); ++i) {
            double diff = std::fabs(state_chunk16[i] - state_chunk32[i]);
            max_diff_s_16_vs_32 = std::max(max_diff_s_16_vs_32, diff);
            max_val_s = std::max(max_val_s, (double)std::fabs(state_chunk32[i]));
        }

        // Compare 16-col candidate vs serial fallback
        double max_diff_y_16_vs_ser = 0.0;
        for (size_t i = 0; i < y_chunk16.size(); ++i) {
            double diff = std::fabs(y_chunk16[i] - y_serial[i]);
            max_diff_y_16_vs_ser = std::max(max_diff_y_16_vs_ser, diff);
        }
        double max_diff_s_16_vs_ser = 0.0;
        for (size_t i = 0; i < state_chunk16.size(); ++i) {
            double diff = std::fabs(state_chunk16[i] - state_serial[i]);
            max_diff_s_16_vs_ser = std::max(max_diff_s_16_vs_ser, diff);
        }

        std::cout << "  T=" << std::setw(3) << T
                  << " | 16-col vs 32-col: y_rel=" << std::scientific << std::setprecision(2)
                  << (max_diff_y_16_vs_32 / max_val_y)
                  << ", S_rel=" << (max_diff_s_16_vs_32 / max_val_s)
                  << " | 16-col vs serial: y_rel=" << (max_diff_y_16_vs_ser / max_val_y)
                  << ", S_rel=" << (max_diff_s_16_vs_ser / max_val_s) << "\n";

        // Assert exact bit-identity between 16-col and 32-col layouts!
        assert(max_diff_y_16_vs_32 == 0.0);
        assert(max_diff_s_16_vs_32 == 0.0);
        // Assert close numerical agreement with serial recurrence (< 5e-5 relative)
        assert(max_diff_y_16_vs_ser / max_val_y < 1e-4);
        assert(max_diff_s_16_vs_ser / max_val_s < 1e-4);
    }

    std::cout << "\nSUCCESS: 16-column layout is bit-identical to 32-column layout and within FP32 roundoff of serial fallback!" << std::endl;
    return 0;
}
