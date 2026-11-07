#!/usr/bin/env python3
"""Benairy aerodynamic design calculations.

Run this file to print the design numbers and to write
docs/generated/design_numbers.md and docs/generated/design_numbers.json.
All units are SI unless the name of a variable says otherwise.
"""
from __future__ import annotations

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# ---------------------------------------------------------------- geometry
P = {
    # Test section
    "ts_width_m": 0.100,
    "ts_height_m": 0.100,
    "ts_length_m": 0.250,
    # Settling chamber (upstream of the contraction)
    "sc_width_m": 0.200,
    "sc_height_m": 0.200,
    "contraction_length_m": 0.200,
    # Honeycomb (printed)
    "hc_cell_m": 0.006,        # across flats
    "hc_wall_m": 0.0008,
    "hc_length_m": 0.040,
    # Screens: window-screen mesh, two layers
    "screen_open_area": 0.60,
    "n_screens": 2,
    # Fan: ARCTIC S12038-8K
    "fan_name": "ARCTIC S12038-8K (120x120x38 mm, PWM, 12 V, 2.2 A)",
    "fan_q_free_cfm": 220.0,
    "fan_dp_max_mmH2O": 37.0,
    "fan_rpm_max": 8000.0,
    "fan_frame_m": 0.120,
    "fan_rotor_d_m": 0.116,
    "fan_hub_d_m": 0.040,
    # Diffuser (square 100 mm to the fan circle)
    "diffuser_length_m": 0.150,
    # Air
    "rho": 1.20,
    "mu": 1.81e-5,
    # Models
    "wing_span_m": 0.080,
    "wing_chord_m": 0.035,
    "car_length_m": 0.075,
    "car_width_m": 0.029,
    "car_height_m": 0.024,
    "car_frontal_fill": 0.85,  # share of the width x height box that is body
    # Strut
    "strut_chord_m": 0.012,
    "strut_thick_m": 0.0035,
    "strut_exposed_m": 0.045,
    # Load cells (100 g bar cells with HX711)
    "cell_rating_g": 100.0,
    "cell_noise_g_rms": 0.010,   # typical HX711 at 10 SPS, after 1 s average
    "cell_nonlin_pct_fs": 0.05,
    "cell_creep_pct_fs": 0.03,
    # Pressure sensor (Sensirion SDP810-125Pa)
    "dp_sensor_name": "Sensirion SDP810-125Pa",
    "dp_range_pa": 125.0,
    "dp_zero_drift_pa": 0.1,
    "dp_span_pct": 3.0,          # of reading
    "dp_resolution_pa": 0.01,
}

G = 9.80665


def area(w, h):
    return w * h


def hydraulic_d(w, h):
    return 2 * w * h / (w + h)


def fan_curve(Q, p):
    """Static pressure rise (Pa) at volume flow Q (m^3/s).

    Shape model for an axial fan: a quadratic from dp_max at Q=0 to 0 at
    the free-air flow. Real axial fans have a stall dip near 40-60 % of
    free-air flow, so the mid-range is optimistic. This is the largest
    single uncertainty in the speed prediction.
    """
    qmax = p["fan_q_free_cfm"] * 0.000471947
    dpmax = p["fan_dp_max_mmH2O"] * 9.80665
    x = Q / qmax
    if x >= 1.0:
        return 0.0
    return dpmax * (1.0 - x ** 2)


def loss_coefficients(p):
    """Loss coefficients referenced to the test-section dynamic pressure."""
    A_ts = area(p["ts_width_m"], p["ts_height_m"])
    A_sc = area(p["sc_width_m"], p["sc_height_m"])
    r = A_ts / A_sc                     # velocity ratio settling/test
    K = {}
    # Honeycomb: K ~ 0.5 at the honeycomb face (Barlow, Rae and Pope),
    # scaled by (V_sc/V_ts)^2.
    beta_hc = (1 - p["hc_wall_m"] / p["hc_cell_m"]) ** 2
    K_hc_local = 0.5 * (1.0 / beta_hc) ** 2 * (p["hc_length_m"] / p["hc_cell_m"]) ** 0.1
    K["honeycomb"] = K_hc_local * r ** 2
    # Screens: K_local ~ 0.65 * (1-beta)/beta^2 for Re_wire > 400.
    beta = p["screen_open_area"]
    K_screen_local = 0.65 * (1 - beta) / beta ** 2
    K["screens"] = p["n_screens"] * K_screen_local * r ** 2
    # Contraction: wall friction, small.
    K["contraction"] = 0.02
    # Test section: f * L / Dh with f ~ 0.02 (smooth printed walls).
    Dh = hydraulic_d(p["ts_width_m"], p["ts_height_m"])
    K["test_section"] = 0.02 * p["ts_length_m"] / Dh
    # Diffuser from the square to the fan circle: short, area ratio ~1.
    A_fan = math.pi / 4 * (p["fan_rotor_d_m"] ** 2 - p["fan_hub_d_m"] ** 2)
    AR = A_fan / A_ts
    K["diffuser"] = 0.15
    # Exit: the air leaves at the fan speed. No exit diffuser.
    K["exit"] = (1.0 / AR) ** 2
    # Model and strut blockage, fan guard.
    K["guard_and_model"] = 0.10
    K["total"] = sum(K.values())
    return K, A_ts, A_fan


def operating_point(p):
    K, A_ts, A_fan = loss_coefficients(p)
    rho = p["rho"]
    # Solve fan_curve(Q) = K_total * 0.5 rho (Q/A_ts)^2 by bisection.
    lo, hi = 0.0, p["fan_q_free_cfm"] * 0.000471947
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        sys_dp = K["total"] * 0.5 * rho * (mid / A_ts) ** 2
        if fan_curve(mid, p) > sys_dp:
            lo = mid
        else:
            hi = mid
    Q = 0.5 * (lo + hi)
    V = Q / A_ts
    q = 0.5 * rho * V ** 2
    return {"Q_m3s": Q, "Q_cfm": Q / 0.000471947, "V_ms": V, "q_pa": q,
            "dp_fan_pa": fan_curve(Q, p), "K": K, "A_ts": A_ts, "A_fan": A_fan}


def model_forces(p, q):
    rho, mu = p["rho"], p["mu"]
    V = math.sqrt(2 * q / rho)
    out = {}
    S = p["wing_span_m"] * p["wing_chord_m"]
    AR = p["wing_span_m"] / p["wing_chord_m"]
    Re_wing = rho * V * p["wing_chord_m"] / mu
    # Low Reynolds number wing: CL_max about 0.8, CD from 0.04 to 0.25.
    out["wing"] = {
        "S_m2": S, "AR": AR, "Re": Re_wing,
        "lift_N_at_CL0.8": 0.8 * q * S,
        "lift_gf_at_CL0.8": 0.8 * q * S / G * 1000,
        "drag_N_at_CD0.04": 0.04 * q * S,
        "drag_gf_at_CD0.04": 0.04 * q * S / G * 1000,
        "drag_gf_at_CD0.25": 0.25 * q * S / G * 1000,
        "blockage_pct_at_15deg": 100 * (p["wing_span_m"] * p["wing_chord_m"]
                                       * math.sin(math.radians(15)) + 0.0035 * 0.012 * 0)
                                 / (p["ts_width_m"] * p["ts_height_m"]),
    }
    A_car = p["car_width_m"] * p["car_height_m"] * p["car_frontal_fill"]
    Re_car = rho * V * p["car_length_m"] / mu
    out["car"] = {
        "A_frontal_m2": A_car, "Re_length": Re_car,
        "drag_N_at_CD0.5": 0.5 * q * A_car,
        "drag_gf_at_CD0.5": 0.5 * q * A_car / G * 1000,
        "lift_gf_at_CL0.2": 0.2 * q * A_car / G * 1000,
        "blockage_pct": 100 * A_car / (p["ts_width_m"] * p["ts_height_m"]),
    }
    # Strut: printed airfoil section, thickness ratio ~0.29, CD ~0.08 on
    # frontal area at this Reynolds number. A round 3 mm rod gives ~1.0.
    A_strut = p["strut_thick_m"] * p["strut_exposed_m"]
    out["strut"] = {
        "drag_gf_airfoil": 0.08 * q * A_strut / G * 1000,
        "drag_gf_round_rod": 1.0 * q * A_strut / G * 1000,
    }
    return out


def balance_budget(p, forces):
    """Resolution and uncertainty of the balance against the forces."""
    rating = p["cell_rating_g"]
    noise = p["cell_noise_g_rms"]
    nonlin = p["cell_nonlin_pct_fs"] / 100 * rating
    creep = p["cell_creep_pct_fs"] / 100 * rating
    # Combined standard uncertainty of a single force reading after tare
    # (tare removes creep and offset to first order; keep half of it).
    u_force_g = math.sqrt(noise ** 2 + nonlin ** 2 + (0.5 * creep) ** 2)
    out = {"u_force_g_1sigma": u_force_g, "noise_g_rms": noise,
           "nonlinearity_g": nonlin, "creep_g": creep}
    out["car_drag_rel_unc_pct"] = 100 * u_force_g / forces["car"]["drag_gf_at_CD0.5"]
    out["wing_lift_rel_unc_pct"] = 100 * u_force_g / forces["wing"]["lift_gf_at_CL0.8"]
    out["wing_drag_rel_unc_pct_CD0.04"] = 100 * u_force_g / forces["wing"]["drag_gf_at_CD0.04"]
    return out


def q_budget(p, q):
    u_zero = p["dp_zero_drift_pa"]
    u_span = p["dp_span_pct"] / 100 * q
    u_q = math.sqrt(u_zero ** 2 + u_span ** 2)
    return {"u_q_pa": u_q, "u_q_rel_pct": 100 * u_q / q,
            "u_V_rel_pct": 50 * u_q / q}


def main():
    op = operating_point(P)
    forces = model_forces(P, op["q_pa"])
    bal = balance_budget(P, forces)
    qb = q_budget(P, op["q_pa"])
    Dh = hydraulic_d(P["ts_width_m"], P["ts_height_m"])
    Re_Dh = P["rho"] * op["V_ms"] * Dh / P["mu"]
    contraction_ratio = (P["sc_width_m"] * P["sc_height_m"]) / op["A_ts"]
    # Boundary layer at the model station (x = 0.18 m from the contraction
    # exit), flat plate, laminar and turbulent bounds.
    x = 0.18
    Re_x = P["rho"] * op["V_ms"] * x / P["mu"]
    delta_lam = 5.0 * x / math.sqrt(Re_x)
    delta_turb = 0.37 * x / Re_x ** 0.2
    # Turbulence reduction: honeycomb + 2 screens, factor ~ 1/sqrt(1+K) each
    f_screen = 1.0 / math.sqrt(1.0 + 0.65 * (1 - P["screen_open_area"]) / P["screen_open_area"] ** 2)
    f_contr = 1.0 / contraction_ratio   # u' reduction roughly 1/c for axial
    result = {
        "parameters": P,
        "operating_point": op,
        "contraction_ratio": contraction_ratio,
        "Re_Dh": Re_Dh,
        "boundary_layer_mm_at_model": {"laminar": delta_lam * 1e3, "turbulent": delta_turb * 1e3},
        "turbulence_factor_screens": f_screen ** P["n_screens"],
        "turbulence_factor_contraction_axial": f_contr,
        "forces": forces,
        "balance_budget": bal,
        "q_budget": qb,
        "fan_power_W_est": 12.0 * 2.2,
    }
    outdir = os.path.join(ROOT, "docs", "generated")
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "design_numbers.json"), "w") as f:
        json.dump(result, f, indent=2)
    lines = []
    lines.append("# Design numbers (generated by tools/design_calcs.py)\n")
    lines.append("Do not edit this file. Run the script again to update it.\n")
    lines.append("## Operating point\n")
    lines.append("| Quantity | Value |\n|---|---|")
    lines.append(f"| Fan | {P['fan_name']} |")
    lines.append(f"| Test section | {P['ts_width_m']*1e3:.0f} x {P['ts_height_m']*1e3:.0f} mm, {P['ts_length_m']*1e3:.0f} mm long |")
    lines.append(f"| Contraction ratio | {contraction_ratio:.1f} |")
    lines.append(f"| Total loss coefficient (on test-section q) | {op['K']['total']:.2f} |")
    lines.append(f"| Volume flow | {op['Q_m3s']:.4f} m^3/s ({op['Q_cfm']:.0f} CFM) |")
    lines.append(f"| Test-section speed | {op['V_ms']:.1f} m/s |")
    lines.append(f"| Dynamic pressure q | {op['q_pa']:.1f} Pa |")
    lines.append(f"| Fan pressure rise at this point | {op['dp_fan_pa']:.0f} Pa |")
    lines.append(f"| Reynolds number on Dh | {Re_Dh:.0f} |")
    lines.append(f"| Floor boundary layer at the model, laminar / turbulent | {delta_lam*1e3:.1f} / {delta_turb*1e3:.1f} mm |")
    lines.append(f"| Turbulence factor, 2 screens x contraction | {f_screen**P['n_screens']*f_contr:.3f} |")
    lines.append("\n## Loss coefficients\n")
    lines.append("| Element | K (on q_ts) |\n|---|---|")
    for k, v in op["K"].items():
        lines.append(f"| {k} | {v:.3f} |")
    w, c, s = forces["wing"], forces["car"], forces["strut"]
    lines.append("\n## Forces at the operating point\n")
    lines.append("| Model | Quantity | Value |\n|---|---|---|")
    lines.append(f"| Wing 80 x 35 mm | Re (chord) | {w['Re']:.0f} |")
    lines.append(f"| Wing 80 x 35 mm | Lift at CL = 0.8 | {w['lift_gf_at_CL0.8']:.2f} gf ({w['lift_N_at_CL0.8']*1e3:.1f} mN) |")
    lines.append(f"| Wing 80 x 35 mm | Drag at CD = 0.04 | {w['drag_gf_at_CD0.04']:.2f} gf |")
    lines.append(f"| Wing 80 x 35 mm | Drag at CD = 0.25 | {w['drag_gf_at_CD0.25']:.2f} gf |")
    lines.append(f"| Wing 80 x 35 mm | Frontal blockage at 15 deg | {w['blockage_pct_at_15deg']:.1f} % |")
    lines.append(f"| 1:64 car | Re (length) | {c['Re_length']:.0f} |")
    lines.append(f"| 1:64 car | Drag at CD = 0.5 | {c['drag_gf_at_CD0.5']:.2f} gf ({c['drag_N_at_CD0.5']*1e3:.1f} mN) |")
    lines.append(f"| 1:64 car | Lift at CL = 0.2 | {c['lift_gf_at_CL0.2']:.2f} gf |")
    lines.append(f"| 1:64 car | Frontal blockage | {c['blockage_pct']:.1f} % |")
    lines.append(f"| Strut, airfoil section | Drag (tare) | {s['drag_gf_airfoil']:.2f} gf |")
    lines.append(f"| Strut, round 3.5 mm rod | Drag (tare) | {s['drag_gf_round_rod']:.2f} gf |")
    lines.append("\n## Balance budget (100 g cells, HX711, 1 s average)\n")
    lines.append("| Quantity | Value |\n|---|---|")
    lines.append(f"| Noise, 1 sigma | {bal['noise_g_rms']:.3f} g |")
    lines.append(f"| Non-linearity | {bal['nonlinearity_g']:.3f} g |")
    lines.append(f"| Creep (half, after tare) | {0.5*bal['creep_g']:.3f} g |")
    lines.append(f"| Combined force uncertainty, 1 sigma | {bal['u_force_g_1sigma']:.3f} g |")
    lines.append(f"| Car drag, relative uncertainty | {bal['car_drag_rel_unc_pct']:.1f} % |")
    lines.append(f"| Wing lift at CL 0.8, relative uncertainty | {bal['wing_lift_rel_unc_pct']:.1f} % |")
    lines.append(f"| Wing drag at CD 0.04, relative uncertainty | {bal['wing_drag_rel_unc_pct_CD0.04']:.1f} % |")
    lines.append("\n## Dynamic pressure budget (SDP810-125Pa)\n")
    lines.append("| Quantity | Value |\n|---|---|")
    lines.append(f"| q uncertainty, 1 sigma | {qb['u_q_pa']:.2f} Pa ({qb['u_q_rel_pct']:.1f} %) |")
    lines.append(f"| Speed uncertainty, 1 sigma | {qb['u_V_rel_pct']:.1f} % |")
    with open(os.path.join(outdir, "design_numbers.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return result


if __name__ == "__main__":
    main()
