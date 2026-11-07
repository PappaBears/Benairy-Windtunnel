#!/usr/bin/env python3
"""Assembly renders of the Benairy wind tunnel from the assembly-frame STLs.

Writes PNG files to cad/renders/. Uses matplotlib only (no OpenGL needed).
"""
from __future__ import annotations

import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "renders")
os.makedirs(OUT, exist_ok=True)

COLORS = {
    "duct": "#9fb4c7", "stack": "#d9c48a", "balance": "#e07b53", "model": "#5aa469",
    "stand": "#7d7d7d", "ref": "#c9a0dc", "misc": "#6fa8dc",
}
GROUP = {
    "bellmouth_quarter": "duct", "settling_chamber": "duct", "contraction_1": "duct", "contraction_2": "duct",
    "test_section_1": "duct", "test_section_2": "duct", "diffuser": "duct", "fan_guard": "duct",
    "honeycomb": "stack", "screen_frame": "stack", "screen_frame_A_pos": "stack", "spacer_12": "stack",
    "spacer_12_pos2": "stack", "spacer_28": "stack",
    "balance_bay": "balance", "platform": "balance", "bracket": "balance", "drum": "balance",
    "strut_long": "balance", "strut_short": "balance",
    "wing_naca0012": "model", "wing_naca4412": "model", "wing_flat_plate": "model", "car_tray": "model",
    "ground_board": "model",
    "stand_settling": "stand", "stand_test_section": "stand", "stand_fan": "stand",
}


def load(name):
    return trimesh.load(os.path.join(HERE, "assembly_stl", name + ".stl"), force="mesh")


def draw(ax, mesh, color, alpha=1.0, lw=0.05, decimate=None):
    m = mesh
    if decimate and len(m.faces) > decimate:
        try:
            m = m.simplify_quadric_decimation(decimate)
        except Exception:
            pass
    tri = m.triangles
    # simple shading by face normal
    n = m.face_normals
    light = np.array([0.4, -0.6, 0.7]); light /= np.linalg.norm(light)
    shade = 0.55 + 0.45 * np.clip(n @ light, 0, 1)
    base = np.array(matplotlib.colors.to_rgb(color))
    fc = np.clip(base[None, :] * shade[:, None], 0, 1)
    fc = np.concatenate([fc, np.full((len(fc), 1), alpha)], axis=1)
    pc = Poly3DCollection(tri, facecolors=fc, edgecolors=(0, 0, 0, 0.08), linewidths=lw)
    ax.add_collection3d(pc)


def set_axes_equal(ax, bounds):
    lo, hi = bounds
    c = (lo + hi) / 2
    r = (hi - lo).max() / 2
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
    ax.set_box_aspect((1, 1, 1))


def scene(names, title, fname, elev=22, azim=-60, clip=None, alpha_duct=1.0, figsize=(14, 8), exclude=()):
    fig = plt.figure(figsize=figsize)
    ax = fig.add_subplot(111, projection="3d")
    allb = []
    for n in names:
        if n in exclude:
            continue
        m = load(n)
        if clip is not None:   # keep the half y < clip (cut-away)
            m = trimesh.intersections.slice_mesh_plane(m, plane_normal=[0, -1, 0], plane_origin=[0, clip, 0], cap=False)
            if m is None or len(m.faces) == 0:
                continue
        g = GROUP.get(n, "ref" if n.startswith("ref_") else "misc")
        a = alpha_duct if g == "duct" else 1.0
        draw(ax, m, COLORS[g], alpha=a, decimate=40000)
        allb.append(m.bounds)
    b = np.array(allb)
    set_axes_equal(ax, (b[:, 0].min(axis=0), b[:, 1].max(axis=0)))
    ax.view_init(elev=elev, azim=azim)
    ax.set_xlabel("x (flow) mm"); ax.set_ylabel("y mm"); ax.set_zlabel("z mm")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, fname), dpi=130)
    plt.close(fig)
    print("wrote", fname)


def main():
    man = json.load(open(os.path.join(HERE, "manifest.json")))
    parts = man["parts"]
    full = [n for n in parts if not n.startswith("ref_") and "_pos" not in n
            and n not in ("electronics_box", "electronics_lid", "cam_clip", "tap_barb", "pitot_wand",
                          "probe_plug", "zero_gauge", "strut_short", "car_tray", "wing_naca4412",
                          "wing_flat_plate", "window_clip")]
    # the bellmouth quarter is stored once; add the other three by mirroring
    scene(full + ["ref_fan", "ref_window_sheet_R"], "Benairy wind tunnel, wing configuration (one bellmouth quarter shown)",
          "assembly_iso.png", elev=20, azim=-55)
    scene(full + ["ref_fan"], "Cut-away at the tunnel centreline (y = 0): flow is left to right",
          "assembly_section.png", elev=8, azim=-90, clip=0.0, figsize=(16, 6))
    bal = ["balance_bay", "platform", "bracket", "drum", "strut_long", "wing_naca0012",
           "ref_servo", "ref_lift_cell", "ref_drag_cell", "ref_as5600"]
    scene(bal, "Force balance in the bay (bay wall cut away at y = 40)", "balance_detail.png",
          elev=18, azim=-40, clip=40.0, figsize=(11, 9))
    scene(["platform", "bracket", "drum", "strut_short", "car_tray", "ground_board", "ref_car",
           "ref_servo", "ref_lift_cell", "ref_drag_cell", "ref_as5600"],
          "Car configuration: short strut, car tray, raised ground board", "car_config.png", elev=18, azim=-35)
    scene(["platform", "bracket", "drum", "ref_servo", "ref_lift_cell", "ref_drag_cell", "ref_as5600"],
          "Metric platform, pitch drum, servo, load cells (bay removed)", "balance_core.png", elev=25, azim=-130)
    # exploded duct: shift each segment along x
    fig = plt.figure(figsize=(16, 6)); ax = fig.add_subplot(111, projection="3d")
    order = ["bellmouth_quarter", "settling_chamber", "spacer_28", "honeycomb", "spacer_12", "screen_frame",
             "contraction_1", "contraction_2", "test_section_1", "test_section_2", "diffuser", "ref_fan", "fan_guard"]
    allb = []
    for i, n in enumerate(order):
        m = load(n)
        m.apply_translation([i * 45.0, 0, 0])
        g = GROUP.get(n, "ref" if n.startswith("ref_") else "misc")
        draw(ax, m, COLORS[g], decimate=30000)
        allb.append(m.bounds)
    b = np.array(allb)
    set_axes_equal(ax, (b[:, 0].min(axis=0), b[:, 1].max(axis=0)))
    ax.view_init(elev=18, azim=-62); ax.set_title("Exploded duct stack (flow left to right)")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "exploded_duct.png"), dpi=130); plt.close(fig)
    print("wrote exploded_duct.png")
    # part gallery
    names = [n for n in parts if not parts[n]["reference"]]
    cols = 6
    rows = (len(names) + cols - 1) // cols
    fig = plt.figure(figsize=(cols * 3.2, rows * 3.0))
    for i, n in enumerate(names):
        ax = fig.add_subplot(rows, cols, i + 1, projection="3d")
        m = trimesh.load(os.path.join(HERE, "stl", n + ".stl"), force="mesh")
        g = GROUP.get(n, "misc")
        draw(ax, m, COLORS[g], decimate=12000)
        set_axes_equal(ax, (m.bounds[0], m.bounds[1]))
        ax.view_init(elev=28, azim=-50)
        ax.set_title("%s\n%.0f x %.0f x %.0f mm" % (n, *m.extents), fontsize=8)
        ax.set_axis_off()
    fig.suptitle("Printed parts in print orientation", fontsize=12)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "parts_gallery.png"), dpi=110); plt.close(fig)
    print("wrote parts_gallery.png")


if __name__ == "__main__":
    main()
