#!/usr/bin/env python3
"""Brand renders of the Benairy wind tunnel from the assembly-frame STLs (matplotlib only)."""
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
BG = "#0B1018"
# finish scheme: graphite duct, cyan accents, slate balance, sand stack, dark fan
COL = {"duct": "#B9C6D6", "accent": "#66E3FF", "balance": "#F0A86A", "model": "#8BE0A0", "stack": "#D9C48A",
       "stand": "#5C6B7F", "fan": "#2A3444", "glass": "#9FD8FF", "misc": "#8FA4BB", "ref": "#C9A0DC"}
GROUP = {"bellmouth_quarter": "accent", "settling_chamber": "duct", "contraction_1": "duct", "contraction_2": "duct",
         "test_section_1": "duct", "test_section_2": "duct", "diffuser": "duct", "fan_guard": "accent", "window_clip": "accent",
         "honeycomb": "stack", "screen_frame": "stack", "screen_frame_A_pos": "stack", "spacer_12": "stack", "spacer_12_pos2": "stack", "spacer_28": "stack",
         "balance_bay": "stand", "platform": "balance", "bracket": "balance", "drum": "accent", "strut_long": "accent", "strut_short": "accent",
         "wing_naca0012": "model", "wing_naca4412": "model", "wing_flat_plate": "model", "car_tray": "model", "ground_board": "model",
         "stand_settling": "stand", "stand_test_section": "stand", "stand_fan": "stand", "electronics_box": "stand", "electronics_lid": "accent",
         "ref_fan": "fan", "ref_window_sheet_R": "glass", "ref_window_sheet_L": "glass", "ref_car": "ref", "ref_servo": "ref",
         "ref_lift_cell": "ref", "ref_drag_cell": "ref", "ref_as5600": "ref"}


def load(name):
    return trimesh.load(os.path.join(HERE, "assembly_stl", name + ".stl"), force="mesh")


def bell_quarters():
    q = load("bellmouth_quarter"); out = [q]
    for sy, sz in ((-1, 1), (1, -1), (-1, -1)):
        m = q.copy(); m.apply_transform(np.diag([1, sy, sz, 1])); m.fix_normals(); out.append(m)
    return out


def draw(ax, m, color, alpha=1.0, decimate=50000, edge=0.0):
    if decimate and len(m.faces) > decimate:
        try: m = m.simplify_quadric_decimation(decimate)
        except Exception: pass
    n = m.face_normals
    key = np.array([0.35, -0.75, 0.55]); key /= np.linalg.norm(key)
    fill = np.array([-0.6, 0.4, 0.3]); fill /= np.linalg.norm(fill)
    shade = 0.42 + 0.48 * np.clip(n @ key, 0, 1) + 0.18 * np.clip(n @ fill, 0, 1)
    base = np.array(matplotlib.colors.to_rgb(color))
    fc = np.clip(base[None, :] * shade[:, None], 0, 1)
    fc = np.concatenate([fc, np.full((len(fc), 1), alpha)], axis=1)
    ax.add_collection3d(Poly3DCollection(m.triangles, facecolors=fc, edgecolors=(0, 0, 0, edge), linewidths=0.05))


def frame(ax, bounds, pad=1.0):
    lo, hi = bounds; c = (lo + hi) / 2; r = (hi - lo).max() / 2 * pad
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
    ax.set_box_aspect((1, 1, 1)); ax.set_axis_off(); ax.set_facecolor(BG)


def scene(meshes, title, fname, elev=22, azim=-60, figsize=(16, 9), subtitle="", pad=0.78, dpi=150):
    fig = plt.figure(figsize=figsize, facecolor=BG); ax = fig.add_subplot(111, projection="3d")
    allb = []
    for m, g in meshes:
        a = 0.35 if g == "glass" else 1.0
        draw(ax, m, COL[g], alpha=a); allb.append(m.bounds)
    b = np.array(allb); frame(ax, (b[:, 0].min(axis=0), b[:, 1].max(axis=0)), pad)
    ax.view_init(elev=elev, azim=azim)
    fig.text(0.04, 0.93, title, color="#EDF4FF", fontsize=18, weight="bold")
    if subtitle: fig.text(0.04, 0.895, subtitle, color="#9FB3C8", fontsize=11)
    fig.text(0.96, 0.04, "Benairy · Schreiber AI", color="#66E3FF", fontsize=10, ha="right")
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    fig.savefig(os.path.join(OUT, fname), dpi=dpi, facecolor=BG); plt.close(fig); print("wrote", fname)


def clip(m, y):
    try:
        c = trimesh.intersections.slice_mesh_plane(m, plane_normal=[0, -1, 0], plane_origin=[0, y, 0], cap=False)
        return c if c is not None and len(c.faces) else None
    except Exception:
        return None


def main():
    parts = json.load(open(os.path.join(HERE, "manifest.json")))["parts"]
    duct = ["settling_chamber", "contraction_1", "contraction_2", "test_section_1", "test_section_2", "diffuser", "fan_guard",
            "window_clip", "stand_settling", "stand_test_section", "stand_fan", "balance_bay", "electronics_box", "electronics_lid",
            "ref_fan", "ref_window_sheet_R", "ref_window_sheet_L", "strut_long", "wing_naca0012"]
    full = [(load(n), GROUP.get(n, "misc")) for n in duct] + [(m, "accent") for m in bell_quarters()]
    scene(full, "Benairy desktop wind tunnel", "hero.png", elev=20, azim=-50, subtitle="100 x 100 mm test section · 9 m/s · two-component balance · ESP32 control", pad=0.72)
    scene(full, "Side view, flow from left to right", "side.png", elev=6, azim=-90, figsize=(18, 7), pad=0.62)
    scene(full, "From the fan end", "rear_quarter.png", elev=18, azim=35, pad=0.72)
    sec = []
    for n in ["settling_chamber", "spacer_28", "honeycomb", "spacer_12", "screen_frame", "contraction_1", "contraction_2", "test_section_1",
              "test_section_2", "diffuser", "fan_guard", "balance_bay", "platform", "bracket", "drum", "strut_long", "wing_naca0012",
              "ref_fan", "ref_servo", "ref_lift_cell", "ref_drag_cell", "stand_settling", "stand_test_section", "stand_fan"]:
        c = clip(load(n), 0.0)
        if c is not None: sec.append((c, GROUP.get(n, "misc")))
    for m in bell_quarters():
        c = clip(m, 0.0)
        if c is not None: sec.append((c, "accent"))
    scene(sec, "Centreline section", "section.png", elev=10, azim=90, figsize=(18, 7), subtitle="honeycomb and screens, 4:1 contraction, test section, balance bay, diffuser, fan cowl", pad=0.6)
    bal = ["balance_bay", "platform", "bracket", "drum", "strut_long", "wing_naca0012", "ref_servo", "ref_lift_cell", "ref_drag_cell", "ref_as5600"]
    bm = []
    for n in bal:
        m = load(n); c = clip(m, 44.0) if n == "balance_bay" else m
        if c is not None: bm.append((c, GROUP.get(n, "misc")))
    scene(bm, "Force balance", "balance.png", elev=20, azim=-38, figsize=(12, 10), subtitle="drag cell (vertical), lift cell (horizontal), metric platform with pitch drum, servo and angle sensor", pad=0.8)
    car = [(load(n), GROUP.get(n, "misc")) for n in ["platform", "bracket", "drum", "strut_short", "car_tray", "ground_board", "ref_car", "ref_servo", "ref_lift_cell", "ref_drag_cell", "ref_as5600"]]
    scene(car, "Car configuration", "car.png", elev=18, azim=-35, figsize=(12, 9), subtitle="short strut, car tray with wheel cut-outs, raised ground board", pad=0.8)
    # exploded duct
    order = ["settling_chamber", "spacer_28", "honeycomb", "spacer_12", "screen_frame", "contraction_1", "contraction_2", "test_section_1", "test_section_2", "diffuser", "ref_fan", "fan_guard"]
    ex = []
    for i, n in enumerate(order):
        m = load(n); m.apply_translation([i * 48.0, 0, 0]); ex.append((m, GROUP.get(n, "misc")))
    for m in bell_quarters():
        m = m.copy(); m.apply_translation([-48.0, 0, 0]); ex.append((m, "accent"))
    scene(ex, "Exploded duct", "exploded.png", elev=16, azim=-62, figsize=(18, 7), pad=0.6)
    # gallery
    names = [n for n in parts if not parts[n]["reference"]]
    cols = 6; rows = (len(names) + cols - 1) // cols
    fig = plt.figure(figsize=(cols * 3.0, rows * 2.9), facecolor=BG)
    for i, n in enumerate(names):
        ax = fig.add_subplot(rows, cols, i + 1, projection="3d")
        m = trimesh.load(os.path.join(HERE, "stl", n + ".stl"), force="mesh")
        draw(ax, m, COL[GROUP.get(n, "misc")], decimate=12000); frame(ax, (m.bounds[0], m.bounds[1]), 0.9)
        ax.view_init(elev=28, azim=-50)
        ax.set_title("%s  %.0f×%.0f×%.0f" % (n, *m.extents), fontsize=7.5, color="#9FB3C8", pad=0)
    fig.text(0.02, 0.985, "Printed parts, print orientation", color="#EDF4FF", fontsize=13, weight="bold", va="top")
    fig.subplots_adjust(left=0.01, right=0.99, bottom=0.01, top=0.95, wspace=0, hspace=0.15)
    fig.savefig(os.path.join(OUT, "parts_gallery.png"), dpi=110, facecolor=BG); plt.close(fig); print("wrote parts_gallery.png")


if __name__ == "__main__":
    main()
