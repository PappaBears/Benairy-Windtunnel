#!/usr/bin/env python3
"""Fit the 2x2 balance calibration matrix from known loads.

Input CSV columns: applied_lift_g, applied_drag_g, lift_raw, drag_raw
(one row per load step; raw values are averages over 2 s, read from the
dashboard Live data tiles or the live log CSV). Positive lift is up,
positive drag is downstream. Hang masses for lift; pull downstream over a
pulley with the same masses for drag. Include zero-load rows at the start,
the middle and the end to capture drift.

    python3 tools/calibrate.py data/examples/sim_calibration.csv --out cal_out

Prints the config values to enter in the dashboard Settings (m11 .. m22).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import benairy_analysis as ba  # noqa: E402

G = 9.80665


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--out", default="cal_out")
    a = ap.parse_args(argv)
    rows = list(csv.DictReader(open(a.csv)))
    L = np.array([float(r["applied_lift_g"]) for r in rows]) * G / 1000
    D = np.array([float(r["applied_drag_g"]) for r in rows]) * G / 1000
    lr = np.array([float(r["lift_raw"]) for r in rows]); dr = np.array([float(r["drag_raw"]) for r in rows])
    fit = ba.fit_calibration(L, D, lr, dr)
    os.makedirs(a.out, exist_ok=True)
    json.dump(fit, open(os.path.join(a.out, "calibration.json"), "w"), indent=2)
    print("points: %d" % fit["n_points"])
    print("sensitivity  lift %.1f counts/N   drag %.1f counts/N" % tuple(fit["sensitivity_counts_per_N"]))
    print("cross talk   drag->lift %.2f %%   lift->drag %.2f %%" % tuple(fit["crosstalk_pct"]))
    print("sensitivity standard error  %.2f %%  %.2f %%" % tuple(fit["se_sensitivity_rel_pct"]))
    print("residual rms  lift %.2f mN   drag %.2f mN   (max %.2f / %.2f mN)" % (
        1000 * fit["residual_rms_n"][0], 1000 * fit["residual_rms_n"][1], 1000 * fit["residual_max_n"][0], 1000 * fit["residual_max_n"][1]))
    print("Enter in the dashboard Settings:")
    for k, v in fit["config_commands"].items():
        print("  %s = %.6e" % (k, v))
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        M = np.array(fit["M"]); r0 = np.array(fit["raw0"])
        Fm = (np.vstack([lr, dr]).T - r0) @ M.T
        fig, ax = plt.subplots(1, 2, figsize=(10, 4))
        ax[0].plot(L * 1000, (Fm[:, 0] - L) * 1000, "o", label="lift"); ax[0].plot(D * 1000, (Fm[:, 1] - D) * 1000, "s", label="drag")
        ax[0].set_xlabel("applied (mN)"); ax[0].set_ylabel("residual (mN)"); ax[0].legend(); ax[0].grid(alpha=.4)
        ax[1].plot(L * 1000, lr - r0[0], "o", label="lift raw vs lift"); ax[1].plot(D * 1000, dr - r0[1], "s", label="drag raw vs drag")
        ax[1].set_xlabel("applied (mN)"); ax[1].set_ylabel("counts"); ax[1].legend(); ax[1].grid(alpha=.4)
        fig.suptitle("Benairy balance calibration · Schreiber AI"); fig.tight_layout()
        fig.savefig(os.path.join(a.out, "calibration.png"), dpi=120)
    except Exception as e:  # pragma: no cover
        print("plot skipped:", e)
    return fit


if __name__ == "__main__":
    main()
