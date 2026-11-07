"""Benairy analysis library: tares, coefficients, wall corrections, uncertainty.

Used by tools/analyze.py and tools/calibrate.py and by the tests.
Units: SI. Angles in degrees unless the name says rad.
"""
from __future__ import annotations

import csv
import io
import json
import math
from dataclasses import dataclass, field

import numpy as np

R_AIR = 287.05


# ------------------------------------------------------------------ CSV I/O
def read_sweep_csv(path_or_text):
    """Read a Benairy sweep CSV (with optional '# key,value' metadata lines).
    Returns (meta dict, list of row dicts with float values)."""
    text = path_or_text if "\n" in path_or_text else open(path_or_text).read()
    meta, lines = {}, []
    for line in text.splitlines():
        if line.startswith("#"):
            kv = line[1:].strip().split(",", 1)
            if len(kv) == 2:
                meta[kv[0].strip()] = kv[1].strip()
        elif line.strip():
            lines.append(line)
    rows = []
    for r in csv.DictReader(io.StringIO("\n".join(lines))):
        rows.append({k: float(v) for k, v in r.items() if v not in (None, "")})
    return meta, rows


def col(rows, key):
    return np.array([r[key] for r in rows], dtype=float)


# ------------------------------------------------------------------ tares
def interp_tare(aoa, tare_rows, key):
    """Interpolate a tare quantity to the given angles (constant outside)."""
    if not tare_rows:
        return np.zeros_like(aoa), np.zeros_like(aoa)
    ta = col(tare_rows, "aoa_deg")
    order = np.argsort(ta)
    ta = ta[order]
    tv = col(tare_rows, key)[order]
    tsd = col(tare_rows, key.replace("_n", "_sd_n"))[order] / np.sqrt(np.maximum(col(tare_rows, "n")[order], 1))
    return np.interp(aoa, ta, tv), np.interp(aoa, ta, tsd)


# ------------------------------------------------------------------ wall corrections
@dataclass
class Tunnel:
    width: float = 0.100
    height: float = 0.100
    delta: float = 0.137     # lift interference factor, closed square section, small span ratio
    tau1: float = 0.87       # body shape factor for solid blockage in a square section
    k1_wing: float = 1.0     # wing solid blockage factor (K1 in Barlow, Rae and Pope)

    @property
    def area(self):
        return self.width * self.height


@dataclass
class Model:
    S: float                 # reference area, m^2 (planform for wings, frontal for cars)
    chord: float = 0.035
    span: float = 0.080
    volume: float = 0.0      # model volume, m^3 (0 -> estimated for a wing from S and chord)
    kind: str = "wing"       # "wing" or "bluff"

    @property
    def AR(self):
        return self.span ** 2 / self.S if self.S > 0 else 0.0


def wall_correct(alpha_u, cl_u, cd_u, q_u, tunnel: Tunnel, model: Model):
    """Closed-test-section corrections (Barlow, Rae and Pope, 3rd ed., ch. 10).

    Returns corrected (alpha, CL, CD, q) and the blockage terms.
    wing: solid blockage from the model volume, wake blockage from CD,
          streamline curvature on alpha and CD.
    bluff (cars): Maskell blockage, CD_c = CD_u / (1 + eta*CD_u*S/C), eta = 2.5.
    """
    C = tunnel.area
    if model.kind == "bluff":
        eps = 2.5 * cd_u * model.S / C
        q_c = q_u * (1 + eps)
        cd_c = cd_u / (1 + eps)
        cl_c = cl_u / (1 + eps)
        return alpha_u, cl_c, cd_c, q_c, {"eps_total": eps, "eps_sb": 0.0, "eps_wb": eps}
    vol = model.volume if model.volume > 0 else 0.7 * model.S * 0.12 * model.chord   # ~NACA 0012 wing volume
    eps_sb = tunnel.k1_wing * tunnel.tau1 * vol / C ** 1.5
    eps_wb = (model.S / (4 * C)) * cd_u
    eps = eps_sb + eps_wb
    q_c = q_u * (1 + eps) ** 2
    d = tunnel.delta * model.S / C
    alpha_c = alpha_u + math.degrees(d * cl_u)
    cd_c = cd_u * (1 - 3 * eps_sb - 2 * eps_wb) + d * cl_u ** 2
    cl_c = cl_u * (1 - 2 * eps)
    return alpha_c, cl_c, cd_c, q_c, {"eps_total": eps, "eps_sb": eps_sb, "eps_wb": eps_wb}


# ------------------------------------------------------------------ uncertainty budget
@dataclass
class Budget:
    u_cal_rel: float = 0.01      # balance calibration, relative (1 sigma)
    u_cross_rel: float = 0.005   # residual cross talk after calibration, fraction of the other axis
    u_q_rel: float = 0.03        # dynamic pressure, relative systematic (sensor span + K_q)
    u_q_abs: float = 0.15        # Pa, zero drift after tare
    u_alpha_b: float = 0.3       # deg, angle zero and strut flex
    u_S_rel: float = 0.01        # reference area
    u_rho_rel: float = 0.005
    k: float = 2.0               # coverage factor for the plots


@dataclass
class Point:
    alpha: float; alpha_c: float; u_alpha: float
    q: float; q_c: float; v: float
    lift: float; drag: float; u_lift: float; u_drag: float
    cl_u: float; cd_u: float; cl: float; cd: float; u_cl: float; u_cd: float
    ld: float; u_ld: float; n: int; eps: dict = field(default_factory=dict)


def analyze(rows, model: Model, tunnel: Tunnel = None, tare_rows=None, strut_rows=None, budget: Budget = None):
    """Full chain: tares -> coefficients -> wall corrections -> uncertainty."""
    tunnel = tunnel or Tunnel(); budget = budget or Budget()
    aoa = col(rows, "aoa_deg"); q = col(rows, "q_pa"); n = col(rows, "n")
    lift = col(rows, "lift_n"); drag = col(rows, "drag_n")
    u_l_a = col(rows, "lift_sd_n") / np.sqrt(np.maximum(n, 1))
    u_d_a = col(rows, "drag_sd_n") / np.sqrt(np.maximum(n, 1))
    u_q_a = col(rows, "q_sd_pa") / np.sqrt(np.maximum(n, 1))
    u_a_a = col(rows, "aoa_sd_deg") / np.sqrt(np.maximum(n, 1))
    # wind-off tare (model installed, fan off): removes residual zero per angle
    tl, utl = interp_tare(aoa, tare_rows or [], "lift_n")
    td, utd = interp_tare(aoa, tare_rows or [], "drag_n")
    # strut tare (wind on, no model) scaled by the q ratio
    if strut_rows:
        sl, usl = interp_tare(aoa, strut_rows, "lift_n"); sd, usd = interp_tare(aoa, strut_rows, "drag_n")
        qs = np.interp(aoa, np.sort(col(strut_rows, "aoa_deg")), col(strut_rows, "q_pa")[np.argsort(col(strut_rows, "aoa_deg"))])
        scale = np.where(qs > 0, q / np.maximum(qs, 1e-9), 1.0)
        sl, sd, usl, usd = sl * scale, sd * scale, usl * scale, usd * scale
    else:
        sl = sd = usl = usd = np.zeros_like(aoa)
    L = lift - tl - sl; D = drag - td - sd
    u_L = np.sqrt(u_l_a ** 2 + utl ** 2 + usl ** 2 + (budget.u_cal_rel * np.abs(L)) ** 2 + (budget.u_cross_rel * np.abs(D)) ** 2)
    u_D = np.sqrt(u_d_a ** 2 + utd ** 2 + usd ** 2 + (budget.u_cal_rel * np.abs(D)) ** 2 + (budget.u_cross_rel * np.abs(L)) ** 2)
    u_q = np.sqrt(u_q_a ** 2 + (budget.u_q_rel * q) ** 2 + budget.u_q_abs ** 2)
    u_alpha = np.sqrt(u_a_a ** 2 + budget.u_alpha_b ** 2)
    pts = []
    for i in range(len(rows)):
        qi = max(q[i], 1e-9)
        cl_u = L[i] / (qi * model.S); cd_u = D[i] / (qi * model.S)
        a_c, cl_c, cd_c, q_c, eps = wall_correct(aoa[i], cl_u, cd_u, qi, tunnel, model)
        # relative uncertainty of a coefficient: force, q, S (correction factors are near 1)
        rel_q = u_q[i] / qi
        u_cl = math.sqrt((u_L[i] / (qi * model.S)) ** 2 + (cl_c * rel_q) ** 2 + (cl_c * budget.u_S_rel) ** 2)
        u_cd = math.sqrt((u_D[i] / (qi * model.S)) ** 2 + (cd_c * rel_q) ** 2 + (cd_c * budget.u_S_rel) ** 2)
        ld = cl_c / cd_c if abs(cd_c) > 1e-9 else 0.0
        u_ld = abs(ld) * math.sqrt((u_cl / cl_c) ** 2 + (u_cd / cd_c) ** 2) if abs(cl_c) > 1e-9 and abs(cd_c) > 1e-9 else 0.0
        rho = rows[i].get("rho_kgm3", 1.2)
        pts.append(Point(aoa[i], a_c, u_alpha[i], qi, q_c, math.sqrt(2 * q_c / rho), L[i], D[i], u_L[i], u_D[i],
                         cl_u, cd_u, cl_c, cd_c, u_cl, u_cd, ld, u_ld, int(n[i]), eps))
    return pts


def fit_lift_slope(pts, cl_limit=0.6):
    """Weighted linear fit CL = a*(alpha - alpha0) in the linear range.
    Returns dict with slope per degree, alpha0, their standard errors and the fit range."""
    sel = [p for p in pts if abs(p.cl) < cl_limit]
    if len(sel) < 3:
        sel = pts
    x = np.array([p.alpha_c for p in sel]); y = np.array([p.cl for p in sel]); w = 1.0 / np.maximum(np.array([p.u_cl for p in sel]), 1e-6) ** 2
    A = np.vstack([x, np.ones_like(x)]).T
    W = np.diag(w)
    cov = np.linalg.inv(A.T @ W @ A)
    beta = cov @ A.T @ W @ y
    resid = y - A @ beta
    dof = max(len(x) - 2, 1)
    s2 = float(resid @ W @ resid) / dof
    cov_scaled = cov * max(s2, 1.0)   # inflate if the scatter is larger than the stated uncertainty
    a, b = beta
    se_a, se_b = math.sqrt(cov_scaled[0, 0]), math.sqrt(cov_scaled[1, 1])
    alpha0 = -b / a if abs(a) > 1e-12 else float("nan")
    se_alpha0 = abs(alpha0) * math.sqrt((se_a / a) ** 2 + (se_b / b) ** 2) if abs(a) > 1e-12 and abs(b) > 1e-12 else se_b / max(abs(a), 1e-12)
    return {"cl_alpha_per_deg": float(a), "se_cl_alpha": se_a, "alpha0_deg": float(alpha0), "se_alpha0": float(se_alpha0),
            "n_points": len(sel), "chi2_reduced": s2, "range_deg": [float(x.min()), float(x.max())]}


def summary(pts, model: Model):
    fit = fit_lift_slope(pts)
    cd = np.array([p.cd for p in pts]); cl = np.array([p.cl for p in pts]); ld = np.array([p.ld for p in pts])
    i_cd0 = int(np.argmin(cd)); i_ld = int(np.argmax(ld)); i_cl = int(np.argmax(cl))
    return {"lift_slope_fit": fit,
            "cd_min": {"value": float(cd[i_cd0]), "u": pts[i_cd0].u_cd, "alpha_deg": pts[i_cd0].alpha_c},
            "cl_max_in_sweep": {"value": float(cl[i_cl]), "u": pts[i_cl].u_cl, "alpha_deg": pts[i_cl].alpha_c},
            "ld_max": {"value": float(ld[i_ld]), "u": pts[i_ld].u_ld, "alpha_deg": pts[i_ld].alpha_c},
            "oswald_e_estimate": _oswald(pts, model),
            "mean_q_pa": float(np.mean([p.q for p in pts])), "mean_v_ms": float(np.mean([p.v for p in pts])),
            "blockage_eps_max": float(max(p.eps.get("eps_total", 0) for p in pts))}


def _oswald(pts, model: Model):
    if model.kind != "wing" or model.AR <= 0:
        return None
    x = np.array([p.cl ** 2 for p in pts]); y = np.array([p.cd for p in pts])
    if len(x) < 3:
        return None
    k, cd0 = np.polyfit(x, y, 1)
    if k <= 0:
        return None
    return {"e": float(1.0 / (math.pi * model.AR * k)), "cd0_fit": float(cd0), "k": float(k)}


def points_to_csv(pts):
    out = ["alpha_deg,alpha_corr_deg,u_alpha_deg,q_pa,q_corr_pa,v_ms,lift_n,drag_n,u_lift_n,u_drag_n,"
           "cl_uncorr,cd_uncorr,cl,cd,u_cl,u_cd,l_over_d,u_l_over_d,eps_blockage,n"]
    for p in pts:
        out.append("%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.6f,%.6f,%.6f,%.6f,%.5f,%.5f,%.5f,%.5f,%.5f,%.5f,%.3f,%.3f,%.5f,%d" % (
            p.alpha, p.alpha_c, p.u_alpha, p.q, p.q_c, p.v, p.lift, p.drag, p.u_lift, p.u_drag, p.cl_u, p.cd_u, p.cl, p.cd,
            p.u_cl, p.u_cd, p.ld, p.u_ld, p.eps.get("eps_total", 0.0), p.n))
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------ calibration
def fit_calibration(applied_lift, applied_drag, lift_raw, drag_raw):
    """Fit raw = A @ F + r0 by least squares; return M = inv(A) (N per count),
    offsets, residuals, cross-talk and coefficient standard errors."""
    F = np.vstack([applied_lift, applied_drag, np.ones(len(applied_lift))]).T   # n x 3
    R = np.vstack([lift_raw, drag_raw]).T                                     # n x 2
    X, res, rank, sv = np.linalg.lstsq(F, R, rcond=None)                      # 3 x 2
    A = X[:2, :].T          # 2x2 counts per N : rows = raw channel, cols = force
    r0 = X[2, :]
    M = np.linalg.inv(A)
    pred = F @ X
    resid = R - pred
    dof = max(len(applied_lift) - 3, 1)
    s2 = (resid ** 2).sum(axis=0) / dof
    cov_base = np.linalg.inv(F.T @ F)
    se = np.sqrt(np.outer(np.diag(cov_base), s2))                             # 3 x 2 standard errors of X
    resid_n = resid @ M.T                                                      # residuals in N
    out = {"M": M.tolist(), "A_counts_per_N": A.tolist(), "raw0": r0.tolist(),
           "sensitivity_counts_per_N": [float(A[0, 0]), float(A[1, 1])],
           "crosstalk_pct": [100 * float(A[0, 1] / A[0, 0]), 100 * float(A[1, 0] / A[1, 1])],
           "se_sensitivity_rel_pct": [100 * float(se[0, 0] / abs(A[0, 0])), 100 * float(se[1, 1] / abs(A[1, 1]))],
           "residual_rms_n": [float(np.sqrt((resid_n[:, 0] ** 2).mean())), float(np.sqrt((resid_n[:, 1] ** 2).mean()))],
           "residual_max_n": [float(np.abs(resid_n[:, 0]).max()), float(np.abs(resid_n[:, 1]).max())],
           "n_points": int(len(applied_lift))}
    out["config_commands"] = {"m11": M[0, 0], "m12": M[0, 1], "m21": M[1, 0], "m22": M[1, 1]}
    return out
