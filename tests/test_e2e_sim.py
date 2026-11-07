"""Simulated end-to-end test: simulation server -> dashboard API -> sweeps ->
CSV export -> analysis -> polar plot. Also checks a fault path (stop loop)
and the client watchdog. The simulation runs 20x faster than real time."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.parse

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze  # noqa: E402


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


class Api:
    def __init__(self, base): self.base = base
    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=5) as r: return r.read().decode()
    def getj(self, path): return json.loads(self.get(path))
    def post(self, path, **params):
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(self.base + path, data=data, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5) as r: return r.status, r.read().decode()
        except urllib.error.HTTPError as e: return e.code, e.read().decode()
    def wait_idle(self, timeout=60):
        t0 = time.time()
        while time.time() - t0 < timeout:
            s = self.getj("/api/status")
            if s["state"] in ("IDLE", "FAULT") and s["sweep_n"] == 0: return s
            time.sleep(0.1)
        raise TimeoutError("sweep did not finish")


@pytest.fixture(scope="module")
def sim():
    port = free_port()
    proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "sim", "server.py"), "--port", str(port), "--speed", "20"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    api = Api("http://127.0.0.1:%d" % port)
    for _ in range(100):
        try:
            if api.getj("/api/info")["sim"]: break
        except Exception: time.sleep(0.1)
    else:
        proc.kill(); raise RuntimeError("sim server did not start: " + proc.stdout.read())
    yield api
    proc.kill()


def test_dashboard_served(sim):
    html = sim.get("/")
    assert "<title>Benairy Control</title>" in html and "Schreiber AI" in html


def test_full_run_and_analysis(sim, tmp_path):
    truth = sim.getj("/api/sim/truth")
    # zero the angle sensor, tare with the fan off
    assert sim.post("/api/cmd", cmd="zero_aoa")[0] == 200
    code, msg = sim.post("/api/cmd", cmd="sweep", list="0,5", fan=0.8)
    assert code == 400 and "tare" in msg                      # sweep refused before tare
    assert sim.post("/api/cmd", cmd="tare")[0] == 200
    time.sleep(0.3)                                            # 2 s sim time at 20x
    assert sim.getj("/api/status")["tared"] == 1
    aoas = "-6,-4,-2,0,2,4,6,8"
    # wind-off tare sweep
    code, msg = sim.post("/api/cmd", cmd="sweep", list=aoas, fan=0, settle=0.5, samples=8)
    assert code == 200, msg
    sim.wait_idle()
    tare_csv = sim.get("/api/sweep.csv")
    # wind-on sweep
    code, msg = sim.post("/api/cmd", cmd="sweep", list=aoas, fan=0.8, settle=1.0, samples=10)
    assert code == 200, msg
    s = sim.getj("/api/status"); assert s["state"] == "SWEEP"
    s = sim.wait_idle()
    assert s["sweep_points"] == 8 and s["fan_out"] == 0
    run_csv = sim.get("/api/sweep.csv")
    assert run_csv.count("\n") == 9
    (tmp_path / "run.csv").write_text("# run,e2e\n# model,sim\n# ref_area_m2,%g\n" % truth["S"] + run_csv)
    (tmp_path / "tare.csv").write_text(tare_csv)
    out = tmp_path / "out"
    summ = analyze.main(["--run", str(tmp_path / "run.csv"), "--tare", str(tmp_path / "tare.csv"), "--out", str(out), "--u-q", "3"])
    assert (out / "polar.png").exists() and (out / "processed.csv").exists() and (out / "summary.json").exists()
    f = summ["lift_slope_fit"]
    # the strut tare is not subtracted here, so compare the lift slope (strut adds drag only)
    assert abs(f["cl_alpha_per_deg"] - truth["cl_alpha_per_deg"]) / truth["cl_alpha_per_deg"] < 0.05, f
    assert abs(f["alpha0_deg"]) < 0.5
    assert 25 < summ["mean_q_pa"] < 40
    # the recovered CD at zero lift equals CD0 plus the strut term within the stated uncertainty
    cd_strut = truth["strut_cd_area"] / truth["S"]
    assert abs(summ["cd_min"]["value"] - (truth["cd0"] + cd_strut)) < 3 * max(summ["cd_min"]["u"], 0.003)


def test_fault_path_stop_loop(sim):
    sim.post("/api/cmd", cmd="clear_faults")
    assert sim.post("/api/cmd", cmd="fan", value=0.5)[0] == 200
    time.sleep(0.2)
    assert sim.getj("/api/status")["state"] == "RUNNING"
    sim.post("/api/sim", estop="1")
    time.sleep(0.2)
    s = sim.getj("/api/status")
    assert s["state"] == "FAULT" and "ESTOP" in s["faults"] and s["fan_out"] == 0
    assert sim.post("/api/cmd", cmd="fan", value=0.5)[0] == 400       # refused in FAULT
    assert sim.post("/api/cmd", cmd="clear_faults")[0] == 400          # loop still open
    sim.post("/api/sim", estop="0")
    assert sim.post("/api/cmd", cmd="clear_faults")[0] == 200
    assert sim.getj("/api/status")["state"] == "IDLE"


def test_client_watchdog(sim):
    sim.post("/api/cmd", cmd="set", key="client_timeout_s", value=3)
    assert sim.post("/api/cmd", cmd="fan", value=0.6)[0] == 200
    time.sleep(0.5)                                             # 10 s sim time without any poll
    s = sim.getj("/api/status")
    assert "CLIENT_TIMEOUT" in s["faults"] and s["fan_out"] == 0
    sim.post("/api/cmd", cmd="clear_faults")
    sim.post("/api/cmd", cmd="set", key="client_timeout_s", value=10)
