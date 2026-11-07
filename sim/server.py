#!/usr/bin/env python3
"""Benairy simulation server: the same HTTP API as the ESP32 firmware, driven by
a virtual tunnel. Lets you use the dashboard and the analysis tools with no
hardware.

    python3 sim/server.py --port 8080
    open http://localhost:8080

Fault injection for tests:  POST /api/sim  estop=1|0  fan_fail=1|0
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tunnel_model import TunnelModel  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASH = os.path.join(ROOT, "dashboard", "index.html")

FAULTS = ["ESTOP", "FAN_STALL", "OVERLOAD_LIFT", "OVERLOAD_DRAG", "CLIENT_TIMEOUT", "SENSOR_STALE", "VBUS_LOW"]


class SimController:
    """Python mirror of firmware/src/controller.cpp (same states, limits, API)."""

    def __init__(self, model: TunnelModel, realtime=True):
        self.m = model
        self.realtime = realtime
        self.cfg = {"m11": 1.0e-6, "m12": 0.0, "m21": 0.0, "m22": 1.0e-6, "kq": 1.067, "p_station_pa": 101325.0,
                    "aoa_zero_deg": 0.0, "aoa_sign": 1.0, "servo_gain": 1.0, "servo_offset_deg": 0.0,
                    "lift_limit_n": 1.5, "drag_limit_n": 0.8, "fan_slew_up": 0.25, "aoa_min": -30.0, "aoa_max": 30.0,
                    "client_timeout_s": 10.0, "vbus_min_v": 10.5, "stall_rpm": 300.0, "stall_grace_s": 3.0, "led_brightness": 0.4, "led_on": 1.0}
        self.state = "IDLE"; self.faults = set()
        self.fan_cmd = 0.0; self.fan_out = 0.0; self.aoa_cmd = 0.0
        self.raw0 = [0, 0]; self.dp0 = 0.0; self.tared = False; self.taring = None
        self.seq = 0; self.ring = []; self.tel = {}
        self.sweep = None; self.sweep_pts = []; self.sweep_i = -1; self.sweep_list = []
        self.sim_estop = False; self.sim_fan_fail = False
        self.last_client = None; self.stall_t = 0.0; self.t = 0.0; self.lock = threading.Lock()
        self.hx_acc = 0.0; self.log = []
        self.sweep_settle_t = 0.0; self.sweep_acc = []

    # ---- commands
    def cmd(self, q):
        c = q.get("cmd", [""])[0]
        g = lambda k, d=0.0: float(q.get(k, [d])[0])
        with self.lock:
            self.last_client = self.t
            if c == "fan":
                if self.state == "FAULT": return 400, "fault active: clear faults first"
                if self.state == "SWEEP": return 400, "sweep running: stop it first"
                self.fan_cmd = max(0.0, min(1.0, g("value"))); self.state = "RUNNING" if self.fan_cmd > 0 else "IDLE"; return 200, "ok"
            if c == "aoa":
                if self.state == "SWEEP": return 400, "sweep running"
                self.aoa_cmd = max(self.cfg["aoa_min"], min(self.cfg["aoa_max"], g("value"))); self.m.set_servo(self.aoa_cmd); return 200, "ok"
            if c == "tare":
                if self.fan_out > 0.02: return 400, "fan must be off (wind-off tare)"
                self.taring = {"t0": self.t, "l": [], "d": [], "dp": []}; return 200, "taring 2 s"
            if c == "zero_aoa":
                self.cfg["aoa_zero_deg"] = self.tel.get("aoa_raw", 0.0); return 200, "ok"
            if c == "stop":
                self.fan_cmd = self.fan_out = 0.0
                if self.state != "FAULT": self.state = "IDLE"
                self.sweep = None; self.sweep_i = -1; return 200, "stopped"
            if c == "clear_faults":
                if self.sim_estop: return 400, "stop loop is open"
                self.faults.clear(); self.state = "IDLE"; self.fan_cmd = self.fan_out = 0.0; self.stall_t = 0; return 200, "ok"
            if c == "light":
                self.cfg["led_on"] = 1.0 if q.get("value", ["1"])[0] not in ("0", "false") else 0.0; return 200, "ok"
            if c == "set":
                k = q.get("key", [""])[0]
                if k not in self.cfg: return 400, "unknown key"
                self.cfg[k] = g("value"); return 200, "ok"
            if c == "sweep":
                if self.state == "FAULT": return 400, "fault active"
                if not self.tared: return 400, "tare first (wind off)"
                try: aoas = [float(x) for x in q.get("list", [""])[0].split(",") if x.strip()]
                except ValueError: return 400, "bad list"
                if not aoas: return 400, "empty list"
                lst = list(aoas)
                if q.get("updown", ["0"])[0] == "1": lst += aoas[-2::-1]
                self.sweep = {"fan": max(0.0, min(1.0, g("fan"))), "settle": g("settle", 2.0), "samples": int(g("samples", 40))}
                self.sweep_list = lst; self.sweep_pts = []; self.sweep_i = 0; self.sweep_settle_t = 0.0; self.sweep_acc = []
                self.fan_cmd = self.sweep["fan"]; self.aoa_cmd = max(self.cfg["aoa_min"], min(self.cfg["aoa_max"], lst[0]))
                self.m.set_servo(self.aoa_cmd); self.state = "SWEEP"; return 200, "ok"
            return 400, "unknown command"

    def fault(self, name):
        if name not in self.faults: self.log.append("FAULT " + name)
        self.faults.add(name); self.state = "FAULT"; self.fan_cmd = self.fan_out = 0.0; self.sweep = None; self.sweep_i = -1

    # ---- 100 Hz tick
    def tick(self, dt=0.01):
        with self.lock:
            self.t += dt
            if self.state != "FAULT":
                if self.fan_cmd > self.fan_out: self.fan_out = min(self.fan_cmd, self.fan_out + self.cfg["fan_slew_up"] * dt)
                else: self.fan_out = self.fan_cmd
            q, lift, drag = self.m.step(dt, self.fan_out)
            s = self.m.sensors(q, lift, drag)
            if self.sim_fan_fail: s["fan_rpm"] = 0.0
            self.hx_acc += dt
            new_sample = self.hx_acc >= 0.1          # 10 SPS HX711
            if new_sample:
                self.hx_acc -= 0.1
                if self.taring:
                    self.taring["l"].append(s["lift_raw"]); self.taring["d"].append(s["drag_raw"]); self.taring["dp"].append(s["dp_pa"])
                    if self.t - self.taring["t0"] >= 2.0:
                        self.raw0 = [sum(self.taring["l"]) / len(self.taring["l"]), sum(self.taring["d"]) / len(self.taring["d"])]
                        self.dp0 = sum(self.taring["dp"]) / len(self.taring["dp"]); self.tared = True; self.taring = None; self.log.append("tare done")
                dl, dd = s["lift_raw"] - self.raw0[0], s["drag_raw"] - self.raw0[1]
                c = self.cfg
                lift_n = c["m11"] * dl + c["m12"] * dd; drag_n = c["m21"] * dl + c["m22"] * dd
                dp = s["dp_pa"] - self.dp0; qm = c["kq"] * dp
                rho = c["p_station_pa"] / (287.05 * (s["temp_c"] + 273.15))
                a = (s["aoa_raw_deg"] - c["aoa_zero_deg"] + 180) % 360 - 180
                self.seq += 1
                self.tel = {"seq": self.seq, "t_ms": int(self.t * 1000), "state": self.state, "faults": ",".join(sorted(self.faults)),
                            "fan_cmd": self.fan_cmd, "fan_out": self.fan_out, "fan_rpm": s["fan_rpm"], "aoa_cmd": self.aoa_cmd,
                            "aoa_deg": c["aoa_sign"] * a, "aoa_raw": s["aoa_raw_deg"], "lift_raw": s["lift_raw"], "drag_raw": s["drag_raw"],
                            "lift_n": lift_n, "drag_n": drag_n, "dp_pa": dp, "q_pa": qm, "v_ms": math.sqrt(max(0.0, 2 * qm / rho)),
                            "temp_c": s["temp_c"], "rho": rho, "vbus": 12.1, "tared": 1 if self.tared else 0}
                self.ring.append(self.tel); self.ring = self.ring[-200:]
                # safety
                if self.sim_estop: self.fault("ESTOP")
                if abs(lift_n) > c["lift_limit_n"]: self.fault("OVERLOAD_LIFT")
                if abs(drag_n) > c["drag_limit_n"]: self.fault("OVERLOAD_DRAG")
                if self.fan_out > 0.25 and s["fan_rpm"] < c["stall_rpm"]: self.stall_t += 0.1
                else: self.stall_t = 0.0
                if self.stall_t > c["stall_grace_s"]: self.fault("FAN_STALL")
                if self.fan_out > 0.05 and self.last_client is not None and c["client_timeout_s"] > 0 and self.t - self.last_client > c["client_timeout_s"]:
                    self.fault("CLIENT_TIMEOUT")
                # sweep
                if self.sweep and self.state == "SWEEP":
                    fan_ready = abs(self.fan_out - self.fan_cmd) < 1e-6
                    if self.sweep_settle_t < self.sweep["settle"] or not fan_ready:
                        if fan_ready: self.sweep_settle_t += 0.1
                    else:
                        self.sweep_acc.append(dict(self.tel))
                        if len(self.sweep_acc) >= self.sweep["samples"]:
                            self.sweep_pts.append(self._point()); self.sweep_acc = []; self.sweep_i += 1
                            if self.sweep_i >= len(self.sweep_list):
                                self.sweep = None; self.sweep_i = -1; self.fan_cmd = 0.0; self.state = "IDLE"; self.log.append("sweep done")
                            else:
                                self.aoa_cmd = max(c["aoa_min"], min(c["aoa_max"], self.sweep_list[self.sweep_i])); self.m.set_servo(self.aoa_cmd); self.sweep_settle_t = 0.0
            self.tel["state"] = self.state; self.tel["faults"] = ",".join(sorted(self.faults))

    def _point(self):
        import statistics as st
        A = self.sweep_acc; n = len(A)
        mean = lambda k: sum(a[k] for a in A) / n
        sd = lambda k: st.stdev([a[k] for a in A]) if n > 1 else 0.0
        q = mean("q_pa"); rho = mean("rho")
        return {"aoa_cmd": self.sweep_list[self.sweep_i], "aoa_deg": mean("aoa_deg"), "aoa_sd": sd("aoa_deg"), "fan_cmd": self.fan_cmd,
                "fan_rpm": mean("fan_rpm"), "q_pa": q, "q_sd": sd("q_pa"), "v_ms": math.sqrt(max(0.0, 2 * q / rho)), "temp_c": mean("temp_c"),
                "rho": rho, "lift_n": mean("lift_n"), "lift_sd": sd("lift_n"), "drag_n": mean("drag_n"), "drag_sd": sd("drag_n"),
                "lift_raw": int(mean("lift_raw")), "drag_raw": int(mean("drag_raw")), "n": n}

    NUM_PIXELS = 24

    def led_frame(self):
        """Mirror of Controller::led_frame: hex colours for the 24 pixels."""
        B = max(0.0, min(1.0, self.cfg["led_brightness"])) * (1.0 if self.cfg["led_on"] > 0.5 else 0.0)
        ph = 0.5 + 0.5 * math.sin(self.t * 2 * math.pi)
        out = []
        for i in range(self.NUM_PIXELS):
            if self.state == "FAULT": k = B * (1.0 if int(self.t * 4) % 2 else 0.15); c = (1.0, 0.1, 0.15)
            elif self.taring: k = B * (0.3 + 0.7 * ph); c = (0.93, 0.96, 1.0)
            elif self.state == "SWEEP":
                prog = self.sweep_i / max(1, len(self.sweep_list))
                if (i + 0.5) / self.NUM_PIXELS <= prog: k = B; c = (1.0, 0.78, 0.43)
                else: k = B * 0.7; c = (0.4, 0.89, 1.0)
            elif self.state == "RUNNING": k = B * (0.5 + 0.5 * self.fan_out); c = (0.4, 0.89, 1.0)
            else: k = B * 0.35; c = (0.55, 0.7, 0.85)
            out.append("%02x%02x%02x" % tuple(int(255 * min(1.0, v * k)) for v in c))
        return "".join(out)

    def status_json(self):
        with self.lock:
            t = dict(self.tel) if self.tel else {"seq": 0, "state": self.state, "faults": ""}
            t.update({"sweep_i": self.sweep_i if self.sweep else -1, "sweep_n": len(self.sweep_list) if self.sweep else 0, "sweep_points": len(self.sweep_pts),
                      "leds": self.led_frame()})
            t.pop("aoa_raw", None)
            return json.dumps(t)

    def samples_json(self, since):
        with self.lock:
            return json.dumps([{k: s[k] for k in ("seq", "t_ms", "lift_n", "drag_n", "q_pa", "aoa_deg", "fan_rpm")} for s in self.ring if s["seq"] > since])

    def sweep_csv(self):
        hdr = "point,aoa_cmd_deg,aoa_deg,aoa_sd_deg,fan_cmd,fan_rpm,q_pa,q_sd_pa,v_ms,temp_c,rho_kgm3,lift_n,lift_sd_n,drag_n,drag_sd_n,lift_raw,drag_raw,n\n"
        rows = []
        for i, p in enumerate(self.sweep_pts):
            rows.append("%d,%.3f,%.3f,%.3f,%.3f,%.0f,%.3f,%.3f,%.3f,%.2f,%.4f,%.6f,%.6f,%.6f,%.6f,%d,%d,%d" % (
                i, p["aoa_cmd"], p["aoa_deg"], p["aoa_sd"], p["fan_cmd"], p["fan_rpm"], p["q_pa"], p["q_sd"], p["v_ms"], p["temp_c"],
                p["rho"], p["lift_n"], p["lift_sd"], p["drag_n"], p["drag_sd"], p["lift_raw"], p["drag_raw"], p["n"]))
        return hdr + "\n".join(rows) + ("\n" if rows else "")


class Handler(BaseHTTPRequestHandler):
    ctl: SimController = None
    speed = 1.0

    def log_message(self, *a):  # quiet
        pass

    def _send(self, code, body, ctype="application/json"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query); c = self.ctl
        if u.path == "/": self._send(200, open(DASH, "rb").read(), "text/html")
        elif u.path == "/api/status":
            with c.lock: c.last_client = c.t
            self._send(200, c.status_json())
        elif u.path == "/api/samples":
            with c.lock: c.last_client = c.t
            self._send(200, c.samples_json(int(q.get("since", ["0"])[0])))
        elif u.path == "/api/config": self._send(200, json.dumps(c.cfg))
        elif u.path == "/api/sweep.csv": self._send(200, c.sweep_csv(), "text/csv")
        elif u.path == "/api/sweep.json": self._send(200, json.dumps(c.sweep_pts))
        elif u.path == "/api/info": self._send(200, json.dumps({"name": "Benairy", "vendor": "Schreiber AI", "fw": "sim-0.1.0", "sim": True, "speed": self.speed}))
        elif u.path == "/api/sim/truth":
            m = c.m; self._send(200, json.dumps({"cl_alpha_per_deg": m.cl_alpha, "alpha0": m.alpha0, "cd0": m.cd0, "S": m.S, "q_max": m.q_max,
                                                 "strut_cd_area": m.strut_cd_area, "kq": m.kq_true, "cross": m.cross, "n_per_count": m.cell_n_per_count}))
        elif u.path == "/api/log": self._send(200, json.dumps(c.log[-50:]))
        else: self._send(404, "not found", "text/plain")

    def do_POST(self):
        u = urlparse(self.path); n = int(self.headers.get("Content-Length", 0)); body = self.rfile.read(n).decode()
        q = parse_qs(body); c = self.ctl
        if u.path == "/api/cmd":
            code, msg = c.cmd(q); self._send(code, msg, "text/plain")
        elif u.path == "/api/sim":
            if "estop" in q: c.sim_estop = q["estop"][0] == "1"
            if "fan_fail" in q: c.sim_fan_fail = q["fan_fail"][0] == "1"
            if "weight_n" in q: c.m.model_weight_n = float(q["weight_n"][0])
            self._send(200, "ok", "text/plain")
        else: self._send(404, "not found", "text/plain")


def run(port=8080, speed=1.0, seed=1):
    model = TunnelModel(seed)
    ctl = SimController(model)
    Handler.ctl = ctl; Handler.speed = speed
    stop = threading.Event()

    def loop():
        nxt = time.monotonic()
        while not stop.is_set():
            ctl.tick(0.01)
            nxt += 0.01 / speed
            d = nxt - time.monotonic()
            if d > 0: time.sleep(d)
            else: nxt = time.monotonic()
    th = threading.Thread(target=loop, daemon=True); th.start()
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("Benairy simulation at http://localhost:%d  (speed x%g)" % (srv.server_address[1], speed), flush=True)
    try: srv.serve_forever()
    except KeyboardInterrupt: pass
    finally: stop.set(); srv.server_close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--speed", type=float, default=1.0, help="simulation speed factor (tests use 20)")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args(); run(a.port, a.speed, a.seed)
