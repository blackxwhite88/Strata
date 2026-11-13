"""tests/split/test_nvlink_tp_proof.py

Unit tests for Phase A deliverables of the SM75 NVLink TP proof:
  1. Exact per-tensor memory budget calculations for Heretic IQ4_XS across 2x 22 GB cards.
  2. SM75 shared memory sizing & numerical recurrence equivalence (GCB=16 vs GCB=32 and serial).
  3. Standalone synthetic peer reduction harness across wire shapes (1, 16, 1024, 4096, odd tails, extremes).
  4. Card check qualification for SM75 (RTX 2080 Ti).
"""
import subprocess
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent.parent


class TestMemoryBudget(unittest.TestCase):
    """Test exact per-tensor memory budget calculations for Qwen3.8-Flash-Next."""

    def test_per_tensor_memory_budget_arithmetic(self):
        layers = 48
        experts = 512
        matrices_per_expert = 3
        hidden = 2560
        ffn_width = 640

        # Total routed weights
        total_routed_weights = layers * experts * matrices_per_expert * hidden * ffn_width
        self.assertEqual(total_routed_weights, 120_795_955_200)

        # IQ4_XS: 136 bytes per 256 weights (4.25 bits/weight)
        iq4_xs_bytes = (total_routed_weights // 256) * 136
        iq4_xs_gib = iq4_xs_bytes / (1024 ** 3)
        self.assertAlmostEqual(iq4_xs_gib, 59.765625, places=4)

        # 2 cards (TP=2)
        routed_per_card_gib = iq4_xs_gib / 2.0
        self.assertAlmostEqual(routed_per_card_gib, 29.8828125, places=4)

        # Card physical capacity: RTX 2080 Ti 22 GB (~21.6 GiB usable)
        card_usable_gib = 21.6
        self.assertGreater(routed_per_card_gib, card_usable_gib)
        deficit = routed_per_card_gib - card_usable_gib
        self.assertAlmostEqual(deficit, 8.2828, places=2)

        # Q2_0 expanded to Q4_0: 18 bytes per 32 weights
        q4_0_bytes = (total_routed_weights // 32) * 18
        q4_0_gib = q4_0_bytes / (1024 ** 3)
        self.assertAlmostEqual(q4_0_gib, 63.28125, places=4)
        q4_0_per_card_gib = q4_0_gib / 2.0
        self.assertAlmostEqual(q4_0_per_card_gib, 31.640625, places=4)


class TestSM75Recurrence(unittest.TestCase):
    """Test SM75 shared memory boundaries and recurrence numerical equivalence."""

    def test_shared_memory_boundaries(self):
        sm75_limit = 64 * 1024  # 65536 bytes
        hs = 128
        gch = 32

        # 1. Serial fallback (k_gdn_pf_rec)
        # xs[2][32][16][8] + vs[32][32] + os[32][32] + gates[32][2] + red[8][32]
        serial_floats = 2 * 32 * 16 * 8 + 32 * 32 + 32 * 32 + 32 * 2 + 8 * 32
        serial_bytes = serial_floats * 4
        self.assertEqual(serial_bytes, 42240)
        self.assertLess(serial_bytes, sm75_limit)

        # 2. Chunked recurrence GCB=32 (SM80 default)
        prep_floats = 2 * gch * gch + 3 * gch + 1
        gcb32_floats = 2 * gch * (hs + 1) + hs * 32 + 4 * gch * 32 + prep_floats
        gcb32_bytes = gcb32_floats * 4
        self.assertEqual(gcb32_bytes, 74372)
        self.assertGreater(gcb32_bytes, sm75_limit)  # Overflows 64 KiB!

        # 3. Chunked recurrence GCB=16 (SM75 candidate)
        gcb16_floats = 2 * gch * (hs + 1) + hs * 16 + 4 * gch * 16 + prep_floats
        gcb16_bytes = gcb16_floats * 4
        self.assertEqual(gcb16_bytes, 57988)
        self.assertLess(gcb16_bytes, sm75_limit)  # Fits within 64 KiB!
        margin = sm75_limit - gcb16_bytes
        self.assertEqual(margin, 7548)

    def test_compiled_sm75_recurrence_binary(self):
        bin_path = Path("/tmp/test_sm75_recurrence")
        if not bin_path.exists():
            cmd = [
                "g++", "-std=c++17", "-O3",
                f"-I{ROOT}/src", f"-I{ROOT}/tests",
                f"{ROOT}/tests/split/test_sm75_recurrence.cpp",
                "-o", str(bin_path)
            ]
            subprocess.run(cmd, check=True)
        res = subprocess.run([str(bin_path)], capture_output=True, text=True, check=True)
        self.assertIn("SUCCESS: 16-column layout is bit-identical to 32-column layout", res.stdout)


class TestPeerReduction(unittest.TestCase):
    """Test standalone synthetic peer reduction across all transports and wire shapes."""

    def test_compiled_peer_reduction_binary(self):
        bin_path = Path("/tmp/test_peer_reduction")
        if not bin_path.exists():
            cmd = [
                "g++", "-std=c++17", "-O3",
                f"{ROOT}/tests/split/test_peer_reduction.cpp",
                "-o", str(bin_path)
            ]
            subprocess.run(cmd, check=True)
        res = subprocess.run([str(bin_path), "--quick"], capture_output=True, text=True, check=True)
        self.assertIn("ALL SYNTHETIC PEER REDUCTION TESTS PASSED", res.stdout)


class TestCardCheckQualification(unittest.TestCase):
    """Test card check qualification for RTX 2080 Ti."""

    def test_card_check_sm75(self):
        bin_path = Path("/tmp/test_card_check")
        cmd = [
            "g++", "-std=c++17",
            f"-I{ROOT}/src/split/src", f"-I{ROOT}/src/split/tools",
            "-DFNX_NCARD=2", "-DFNX_27B=0",
            f"{ROOT}/src/split/tools/card_check_test.cpp",
            "-o", str(bin_path)
        ]
        subprocess.run(cmd, check=True)
        res = subprocess.run([str(bin_path)], capture_output=True, text=True, check=True)
        self.assertIn("card_check_test: ok", res.stdout)


if __name__ == "__main__":
    unittest.main()
