"""Virtual Benairy tunnel: fan, losses, model aerodynamics and sensor noise.

Shared by the simulation server (sim/server.py) and the tests. The truth
values (CL slope, CD0, strut tare) are known, so the analysis tools can be
checked end to end.
"""
from __future__ import annotations

import math
import random

G = 9.80665


class TunnelModel:
    def __init__(self, seed=1):
        self.rng = random.Random(seed)
        # tunnel
        self.q_max = 50.0           # Pa at full fan (from tools/design_calcs.py)
        self.kq_true = 1.067
        self.rho = 1.19
        # wing truth (NACA 0012, 80 x 35 mm, Re 21 000)
        self.S = 0.0028
        self.cl_alpha = 0.075       # per deg (finite wing AR 2.3)
        self.alpha0 = 0.0
        self.cl_max = 0.85
        self.cd0 = 0.030
        self.e_ar = 0.9 * math.pi * 2.29
        # strut and tray tares (fixed, wind-on)
        self.strut_cd_area = 0.08 * 0.0045 * 0.050     # CD * frontal area
        # model weight and balance offsets
        self.model_weight_n = 0.08
        self.cell_n_per_count = 1.0e-6                 # true calibration
        self.cross = 0.02                              # 2 % cross talk drag->lift
        self.off_l, self.off_d = 123456, -98765
        self.noise_counts = 12.0                       # HX711 noise 1 sigma
        self.dp_noise = 0.05
        self.dp_offset = 0.8
        self.aoa_zero = 137.2
        self.aoa_noise = 0.05
        self.servo_tau = 0.25
        # state
        self.fan_out = 0.0
        self.aoa_true = 0.0
        self.aoa_servo_cmd = 0.0
        self.drift = 0.0
        self.t = 0.0

    def set_servo(self, deg):
        self.aoa_servo_cmd = deg

    def coefficients(self, a):
        a_eff = a - self.alpha0
        cl = self.cl_alpha * a_eff
        if abs(cl) > self.cl_max:  # soft stall
            cl = math.copysign(self.cl_max - 0.02 * (abs(a_eff) - self.cl_max / self.cl_alpha), cl)
        cd = self.cd0 + cl * cl / self.e_ar
        return cl, cd

    # closed-test-section wall interference (same constants as benairy_analysis)
    C = 0.100 * 0.100
    delta = 0.137
    tau1 = 0.87

    def tunnel_coefficients(self, alpha_geom):
        """In-tunnel (uncorrected) CL, CD at a geometric angle, from the free-air
        truth: upwash raises the effective angle, blockage raises q, streamline
        curvature lowers the measured drag. Inverse of benairy_analysis.wall_correct."""
        d = self.delta * self.S / self.C
        vol = 0.7 * self.S * 0.12 * 0.035
        eps_sb = self.tau1 * vol / self.C ** 1.5
        cl_u, cd_u = self.coefficients(alpha_geom)
        for _ in range(3):
            d_alpha = math.degrees(d * cl_u)
            cl_f, cd_f = self.coefficients(alpha_geom + d_alpha)
            eps_wb = (self.S / (4 * self.C)) * cd_u
            eps = eps_sb + eps_wb
            cl_u = cl_f / (1 - 2 * eps)
            cd_u = (cd_f - d * cl_u ** 2) / (1 - 3 * eps_sb - 2 * eps_wb)
        return cl_u, cd_u

    def step(self, dt, fan_cmd):
        self.t += dt
        self.fan_out = fan_cmd
        self.aoa_true += (self.aoa_servo_cmd - self.aoa_true) * min(1.0, dt / self.servo_tau)
        self.drift += self.rng.gauss(0, 0.3) * dt       # slow zero drift, counts/s
        q = self.q_max * self.fan_out ** 2              # q measured by the contraction taps
        cl, cd = self.tunnel_coefficients(self.aoa_true)
        lift = q * self.S * cl
        drag = q * self.S * cd + q * self.strut_cd_area
        return q, lift, drag

    def sensors(self, q, lift, drag):
        rng = self.rng
        lift_total = lift - self.model_weight_n            # weight pulls down (negative lift)
        cl_counts = (lift_total + self.cross * drag) / self.cell_n_per_count
        cd_counts = drag / self.cell_n_per_count
        return {
            "lift_raw": int(self.off_l + cl_counts + self.drift + rng.gauss(0, self.noise_counts)),
            "drag_raw": int(self.off_d + cd_counts + self.drift * 0.5 + rng.gauss(0, self.noise_counts)),
            "dp_pa": q / self.kq_true + self.dp_offset + rng.gauss(0, self.dp_noise),
            "temp_c": 21.5 + 0.3 * math.sin(self.t / 60),
            "aoa_raw_deg": (self.aoa_zero + self.aoa_true + rng.gauss(0, self.aoa_noise)) % 360,
            "fan_rpm": 8000 * self.fan_out + rng.gauss(0, 20) if self.fan_out > 0.05 else 0.0,
        }
