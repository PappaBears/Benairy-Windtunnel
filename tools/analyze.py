#!/usr/bin/env python3
"""Make corrected polar plots with uncertainty from Benairy sweep CSV files.

Example
    python3 tools/analyze.py --run data/examples/sim_wing_run.csv \
        --tare data/examples/sim_wing_tare.csv --area 0.0028 --chord 0.035 --span 0.080 \
        --out data/examples/out

Writes <out>/polar.png, <out>/processed.csv, <out>/summary.json.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import benairy_analysis as ba  # noqa: E402


def make_plots(pts, summary, out_png, title, k=2.0):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    bg, panel, text, cyan, amber, red, muted = "#0B1018", "#152234", "#EDF4FF", "#66E3FF", "#FFC66D", "#FF707D", "#9FB3C8"
    plt.rcParams.update({"figure.facecolor": bg, "axes.facecolor": panel, "axes.edgecolor": muted, "axes.labelcolor": text,
                         "xtick.color": muted, "ytick.color": muted, "text.color": text, "grid.color": "#223349", "font.size": 10})
    a = [p.alpha_c for p in pts]; ua = [k * p.u_alpha for p in pts]
    cl = [p.cl for p in pts]; ucl = [k * p.u_cl for p in pts]
    cd = [p.cd for p in pts]; ucd = [k * p.u_cd for p in pts]
    ld = [p.ld for p in pts]; uld = [k * p.u_ld for p in pts]
    fig, ax = plt.subplots(2, 2, figsize=(12, 8.5))
    ax[0, 0].errorbar(a, cl, xerr=ua, yerr=ucl, fmt="o-", color=cyan, ecolor=muted, capsize=2, ms=4)
    f = summary["lift_slope_fit"]
    xs = f["range_deg"]
    ax[0, 0].plot(xs, [f["cl_alpha_per_deg"] * (x - f["alpha0_deg"]) for x in xs], "--", color=amber,
                  label="fit: dCL/dα = %.4f ± %.4f /deg, α0 = %.2f ± %.2f°" % (f["cl_alpha_per_deg"], f["se_cl_alpha"], f["alpha0_deg"], f["se_alpha0"]))
    ax[0, 0].set_xlabel("α corrected (deg)"); ax[0, 0].set_ylabel("CL"); ax[0, 0].legend(fontsize=8, facecolor=panel)
    ax[0, 1].errorbar(a, cd, xerr=ua, yerr=ucd, fmt="o-", color=amber, ecolor=muted, capsize=2, ms=4)
    ax[0, 1].set_xlabel("α corrected (deg)"); ax[0, 1].set_ylabel("CD")
    ax[1, 0].errorbar(cd, cl, xerr=ucd, yerr=ucl, fmt="o-", color=cyan, ecolor=muted, capsize=2, ms=4)
    ax[1, 0].set_xlabel("CD"); ax[1, 0].set_ylabel("CL"); ax[1, 0].set_title("Drag polar", color=muted, fontsize=10)
    ax[1, 1].errorbar(a, ld, xerr=ua, yerr=uld, fmt="o-", color=red, ecolor=muted, capsize=2, ms=4)
    ax[1, 1].set_xlabel("α corrected (deg)"); ax[1, 1].set_ylabel("L/D")
    for axx in ax.flat:
        axx.grid(True, alpha=0.5)
    fig.suptitle("%s   (error bars: k = %g expanded uncertainty)" % (title, k), color=text)
    fig.text(0.99, 0.01, "Benairy · Schreiber AI", ha="right", color=muted, fontsize=8)
    fig.tight_layout(rect=(0, 0.02, 1, 0.96))
    fig.savefig(out_png, dpi=130); plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, help="wind-on sweep CSV")
    ap.add_argument("--tare", help="wind-off sweep CSV with the model installed (fan 0)")
    ap.add_argument("--strut", help="wind-on sweep CSV without the model (strut tare)")
    ap.add_argument("--area", type=float, help="reference area m^2 (default: from the CSV metadata)")
    ap.add_argument("--chord", type=float, default=0.035)
    ap.add_argument("--span", type=float, default=0.080)
    ap.add_argument("--volume", type=float, default=0.0, help="model volume m^3 for solid blockage (0 = estimate)")
    ap.add_argument("--kind", choices=["wing", "bluff"], default="wing")
    ap.add_argument("--u-cal", type=float, default=1.0, help="balance calibration uncertainty, %% (1 sigma)")
    ap.add_argument("--u-q", type=float, default=3.0, help="dynamic pressure systematic uncertainty, %% (1 sigma)")
    ap.add_argument("--u-alpha", type=float, default=0.3, help="angle systematic uncertainty, deg (1 sigma)")
    ap.add_argument("--k", type=float, default=2.0, help="coverage factor for the plots")
    ap.add_argument("--out", default="analysis_out")
    ap.add_argument("--title", default=None)
    a = ap.parse_args(argv)
    meta, rows = ba.read_sweep_csv(a.run)
    tare = ba.read_sweep_csv(a.tare)[1] if a.tare else None
    strut = ba.read_sweep_csv(a.strut)[1] if a.strut else None
    S = a.area or float(meta.get("ref_area_m2", 0) or 0)
    if S <= 0:
        sys.exit("reference area unknown: pass --area")
    chord = float(meta.get("ref_chord_m", a.chord) or a.chord)
    model = ba.Model(S=S, chord=chord, span=a.span, volume=a.volume, kind=a.kind)
    budget = ba.Budget(u_cal_rel=a.u_cal / 100, u_q_rel=a.u_q / 100, u_alpha_b=a.u_alpha, k=a.k)
    pts = ba.analyze(rows, model, tare_rows=tare, strut_rows=strut, budget=budget)
    summ = ba.summary(pts, model)
    summ["inputs"] = {"run": a.run, "tare": a.tare, "strut": a.strut, "meta": meta, "model": model.__dict__, "budget": budget.__dict__}
    os.makedirs(a.out, exist_ok=True)
    open(os.path.join(a.out, "processed.csv"), "w").write(ba.points_to_csv(pts))
    json.dump(summ, open(os.path.join(a.out, "summary.json"), "w"), indent=2)
    title = a.title or "%s %s" % (meta.get("run", os.path.basename(a.run)), meta.get("model", ""))
    make_plots(pts, summ, os.path.join(a.out, "polar.png"), title, k=a.k)
    f = summ["lift_slope_fit"]
    print("points: %d   mean q: %.1f Pa   mean V: %.2f m/s" % (len(pts), summ["mean_q_pa"], summ["mean_v_ms"]))
    print("dCL/dalpha = %.4f +- %.4f per deg   alpha0 = %.2f +- %.2f deg" % (f["cl_alpha_per_deg"], f["se_cl_alpha"], f["alpha0_deg"], f["se_alpha0"]))
    print("CD min = %.4f +- %.4f at %.1f deg   L/D max = %.2f +- %.2f at %.1f deg" % (
        summ["cd_min"]["value"], summ["cd_min"]["u"], summ["cd_min"]["alpha_deg"], summ["ld_max"]["value"], summ["ld_max"]["u"], summ["ld_max"]["alpha_deg"]))
    print("max blockage correction eps = %.3f" % summ["blockage_eps_max"])
    print("written:", a.out)
    return summ


if __name__ == "__main__":
    main()
