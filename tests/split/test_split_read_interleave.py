"""CPU checks of the server's bounded prompt/decode fairness policy."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ReadInterleave(unittest.TestCase):
    @unittest.skipUnless(shutil.which("g++"), "needs g++")
    def test_budget_chunk_limits_and_flag_parsing(self):
        with tempfile.TemporaryDirectory(prefix="split-interleave-") as tmp:
            exe = Path(tmp) / "budget-test"
            subprocess.run([
                "g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
                "-I", str(ROOT / "src/split/src"),
                str(ROOT / "tests/split/read_interleave_test.cpp"), "-o", str(exe),
            ], check=True, capture_output=True, text=True, timeout=30)
            env = {k: v for k, v in os.environ.items() if not k.startswith("FNX_READ_")}
            subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=10, env=env)
