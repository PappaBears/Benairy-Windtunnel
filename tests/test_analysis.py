"""Analysis library tests on synthetic data with known truth."""
import math
import random

import numpy as np

import benairy_analysis as ba
from tunnel_model import TunnelModel


def synth_sweep(model: TunnelModel, aoas, fan, n=40, seed=3):
    rng = random.Random(seed)
    rows = []
    for a in aoas:
        q = model.q_max * fan ** 2
        cl, cd = model.tunnel_coefficients(a)
        L = q * model.S * cl; D = q * model.S * cd + q * model.strut_cd_area
        Ls = [L + rng.gauss(0, 12e-6) for _ in range(n)]; Ds = [D + rng.gauss(0, 12e-6) for _ in range(n)]
        qs = [q + rng.gauss(0, 0.05) for _ in range(n)]
        rows.append({"aoa_deg": a + rng.gauss(0, 0.02), "aoa_sd_deg": 0.05, "q_pa": float(np.mean(qs)), "q_sd_pa": float(np.std(qs)),
                     "lift_n": float(np.mean(Ls)), "lift_sd_n": float(np.std(Ls)), "drag_n": float(np.mean(Ds)), "drag_sd_n": float(np.std(Ds)),
                     "n": n, "rho_kgm3": 1.19})
    return rows


def test_lift_slope_recovered_with_strut_tare():
    m = TunnelModel(seed=2)
    aoas = [-6, -4, -2, 0, 2, 4, 6, 8]
    run = synth_sweep(m, aoas, 0.8)
    # strut-only run: no model forces, only the strut drag
    strut = []
    for r in synth_sweep(m, aoas, 0.8, seed=5):
        q = r["q_pa"]; r = dict(r); r["lift_n"] = 0.0; r["drag_n"] = q * m.strut_cd_area; strut.append(r)
    model = ba.Model(S=m.S, chord=0.035, span=0.080)
    pts = ba.analyze(run, model, strut_rows=strut)
    s = ba.summary(pts, model)
    f = s["lift_slope_fit"]
    # the synthetic data carry wall interference; the corrected results must match the free-air truth
    x = np.array([p.alpha for p in pts]); y = np.array([p.cl_u for p in pts])
    slope_u = np.polyfit(x, y, 1)[0]
    assert slope_u > m.cl_alpha * 1.05                                      # uncorrected slope is too high
    assert abs(f["cl_alpha_per_deg"] - m.cl_alpha) / m.cl_alpha < 0.03      # corrected slope within 3 %
    assert abs(f["alpha0_deg"]) < 0.3
    cd0 = min(p.cd for p in pts)
    assert abs(cd0 - m.cd0) < 0.003
    assert all(p.u_cl > 0 and p.u_cd > 0 for p in pts)
    # uncertainty should be dominated by q (3 %) at high CL: u_cl/cl ~ 3-4 %
    p = pts[-1]
    assert 0.025 < p.u_cl / p.cl < 0.06


def test_wall_correction_directions():
    t = ba.Tunnel(); mdl = ba.Model(S=0.0028, chord=0.035, span=0.08)
    a, cl, cd, q, eps = ba.wall_correct(5.0, 0.5, 0.05, 50.0, t, mdl)
    assert a > 5.0                  # upwash correction increases alpha for positive lift
    assert q > 50.0                 # blockage increases effective q
    assert cl < 0.5                 # CL decreases
    assert 0 < eps["eps_total"] < 0.05
    a2, cl2, cd2, q2, eps2 = ba.wall_correct(0.0, 0.1, 0.5, 50.0, t, ba.Model(S=6e-4, kind="bluff"))
    assert cd2 < 0.5 and q2 > 50.0


def test_calibration_fit_recovers_matrix():
    rng = random.Random(7)
    A = np.array([[1.0e6, 2.0e4], [-1.0e4, 1.0e6]])     # counts per N, with cross talk
    r0 = np.array([123456.0, -98765.0])
    L, D, lr, dr = [], [], [], []
    for g in [0, 5, 10, 20, 0, 5, 10, 20, 0]:
        f = g * 9.80665 / 1000
        for (fl, fd) in ((f, 0.0), (0.0, f)):
            raw = A @ np.array([fl, fd]) + r0 + np.array([rng.gauss(0, 10), rng.gauss(0, 10)])
            L.append(fl); D.append(fd); lr.append(raw[0]); dr.append(raw[1])
    fit = ba.fit_calibration(np.array(L), np.array(D), np.array(lr), np.array(dr))
    M = np.array(fit["M"])
    assert np.allclose(M @ A, np.eye(2), atol=2e-3)
    assert abs(fit["crosstalk_pct"][0] - 2.0) < 0.2
    assert fit["residual_rms_n"][0] < 5e-5
    assert fit["se_sensitivity_rel_pct"][0] < 0.5


def test_csv_roundtrip(tmp_path):
    text = "# run,x\n# ref_area_m2,0.0028\npoint,aoa_deg,q_pa,n\n0,1.5,50,10\n1,2.5,51,10\n"
    p = tmp_path / "a.csv"; p.write_text(text)
    meta, rows = ba.read_sweep_csv(str(p))
    assert meta["ref_area_m2"] == "0.0028" and len(rows) == 2 and rows[1]["aoa_deg"] == 2.5
