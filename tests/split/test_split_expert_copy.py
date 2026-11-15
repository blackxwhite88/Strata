"""CPU checks of the copy service; no CUDA toolkit, driver or GPU execution."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class CopyHost(unittest.TestCase):
    @unittest.skipUnless(shutil.which("g++"), "needs g++")
    def test_handoff_fallback_slot_reuse_and_errors(self):
        with tempfile.TemporaryDirectory(prefix="split-copy-") as tmp:
            stage = Path(tmp)
            fake = ROOT / "tests/split/expert_copy_fake_cuda.hpp"
            (stage / "cuda_runtime.h").write_text(f'#include "{fake}"\n')
            exe = stage / "host-test"
            subprocess.run([
                "g++", "-std=c++17", "-O2", "-pthread", "-Wall", "-Wextra", "-Werror",
                "-DFNX_NCARD=2", "-DFNX_27B=0", "-DFNX_HIP=0",
                "-I", str(stage), "-I", str(ROOT / "src/split/src"),
                str(ROOT / "tests/split/expert_copy_host_test.cpp"), "-o", str(exe),
            ], check=True, capture_output=True, text=True, timeout=30)
            subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=10)
