"""Builds and runs the firmware controller unit tests on the host (g++)."""
import os
import shutil
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_controller_host_tests():
    if not shutil.which("g++") or not shutil.which("make"):
        import pytest
        pytest.skip("g++/make not available")
    r = subprocess.run(["make", "-s", "test"], cwd=os.path.join(ROOT, "firmware", "test_host"), capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "ALL CONTROLLER TESTS PASSED" in r.stdout
