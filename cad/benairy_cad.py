#!/usr/bin/env python3
"""Benairy desktop wind tunnel: parametric CAD generator.

Run with plain Python (CadQuery backend) or inside FreeCAD (FreeCAD
backend, also writes Benairy.FCStd with a parameter spreadsheet):

    python3 cad/benairy_cad.py                 # STL + STEP to cad/stl, cad/step
    freecadcmd cad/benairy_cad.py              # same, plus cad/Benairy.FCStd

Coordinate system (assembly frame, millimetres):
    x  downstream (flow direction)
    y  to the right when you look downstream
    z  up
    origin: centre of the test-section inlet plane (contraction exit)

Every part is built in the assembly frame. A print orientation (rotation
about an axis) is attached to each part. The export step rotates the part
and puts its lowest face on z = 0 for the slicer.

Edit PARAMS to change the design. All downstream parts (flanges, bolt
patterns, slots) follow from PARAMS.
"""
from __future__ import annotations

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

try:  # FreeCAD first: it has its own Python.
    import FreeCAD  # noqa: F401
    from kernel_freecad import Kernel, make_document
    IN_FREECAD = True
except ImportError:
    from kernel_cq import Kernel
    make_document = None
    IN_FREECAD = False

K = Kernel()

# ====================================================================== PARAMS
PARAMS = {
    # ---- printer
    "bed": 256.0,
    # ---- duct
    "ts_half": 50.0,            # test section half width (100 x 100 mm)
    "ts1_len": 120.0,           # upstream test section segment
    "ts2_len": 130.0,           # balance segment
    "sc_half": 100.0,           # settling chamber half width
    "sc_len": 100.0,
    "contraction_len": 200.0,
    "wall": 2.0,
    "flange_w": 8.0,
    "flange_t": 3.2,
    "bolt_d": 3.4,              # M3 clearance
    "bell_r": 22.0,             # bellmouth lip radius
    "bell_t": 22.0,
    "bell_outer_half": 125.0,
    # ---- honeycomb and screens
    "hc_cell": 6.0,             # across flats
    "hc_wall": 0.5,
    "hc_len": 36.0,
    "hc_rim": 3.0,
    "stack_clear": 0.5,         # radial clearance of inserts in the chamber
    "spacer_wall": 4.0,
    "screen_t": 2.5,
    "screen_frame_w": 5.5,
    "lip_w": 2.0,
    "lip_t": 3.0,
    # ---- diffuser and fan
    "diff_len": 150.0,
    "fan_frame": 120.0,
    "fan_bore": 116.0,
    "fan_hole_pitch": 105.0,
    "fan_bolt_d": 4.4,
    "fan_plate_half": 65.0,
    "fan_plate_t": 5.0,
    "fan_depth": 38.0,
    "guard_t": 6.0,
    "guard_rings": 5,
    "guard_spokes": 12,
    "guard_bar": 2.4,
    # ---- test section details
    "window_x0": 140.0, "window_x1": 230.0, "window_half_z": 32.0,
    "window_recess": 1.2, "window_margin": 5.0, "window_boss": 2.0, "window_boss_w": 18.0,
    "magnet_d": 6.0, "magnet_t": 2.0,      # user's magnets, change to match
    "tap_d": 1.2,
    "probe_hole_d": 5.0,
    "model_x": 185.0,           # model station
    "slot_x_half": 15.0, "slot_y_half": 4.0,
    "bay_bolt_x": (140.0, 230.0), "bay_bolt_y": 45.0,
    "gb_peg_x": (150.0, 220.0), "gb_peg_y": 35.0, "gb_peg_d": 2.0, "gb_peg_hole_d": 2.3,
    # ---- balance bay
    "bay_x0": 125.0, "bay_x1": 245.0,
    "bay_half_y": 53.0,
    "bay_depth": 80.0,          # from the floor underside down to the table
    "bay_base_t": 4.0,
    "bay_lip_w": 8.0,
    # ---- load cells (measure yours and update)
    "cell_L": 45.0, "cell_w": 6.4, "cell_t": 6.4,
    "cell_hole_d": 2.2, "cell_holes": (4.5, 10.5),   # from each end
    # ---- pitch drum and servo
    "drum_r": 10.0, "drum_half_w": 6.0,
    "drum_z": -65.0,            # axis height (floor underside is -53)
    "stub_d": 8.0, "stub_len": 6.0, "stub_hole_clear": 0.3,
    "servo_L": 22.5, "servo_W": 12.0, "servo_H": 22.8,  # MG90S body
    "servo_shaft_from_end": 6.0, "servo_flange_from_top": 6.8,
    "servo_flange_t": 2.5, "servo_tab": 5.0, "servo_tab_hole_d": 2.0,
    "servo_horn_gap": 2.0,
    # ---- strut
    "strut_chord": 14.0, "strut_t": 4.5,
    "tongue_w": 6.0, "tongue_t": 3.0, "tongue_h": 6.0, "tongue_clear": 0.2,
    "pin_d": 1.6,
    "wing_z": 3.0,              # chord line height of the wing (model centre)
    "car_tray_z": -37.0,        # underside of the car tray
    "ground_board_top": -38.5, "ground_board_t": 3.0,
    "ground_board_x": (140.0, 230.0), "ground_board_slot": (36.0, 10.0),
    "ground_board_bevel": 12.0,
    # ---- models
    "wing_chord": 35.0, "wing_span": 80.0, "wing_te_min": 0.8,
    "pylon_t": 6.0,
    "car_len": 75.0, "car_w": 32.0, "tray_t": 2.5,
    "car_wheelbase": 45.0, "car_track": 22.0, "car_wheel_d": 9.0,
    # ---- overload stops
    "stop_gap": 0.6,
    # ---- stands
    "table_z": None,            # derived: floor underside - bay depth
    # ---- electronics box
    "ebox_inner": (110.0, 75.0, 35.0), "ebox_wall": 2.4,
}
P = PARAMS

# Derived positions along x (assembly frame)
X_TS0 = 0.0
X_TS1 = P["ts1_len"]                               # 120
X_TS2 = P["ts1_len"] + P["ts2_len"]                # 250
X_C_IN = -P["contraction_len"]                      # -200
X_C_MID = -P["contraction_len"] / 2                 # -100
X_SC_IN = X_C_IN - P["sc_len"]                      # -300
X_BELL = X_SC_IN - P["bell_t"]                      # -322
X_DIFF1 = X_TS2 + P["diff_len"]                     # 400
X_FAN_PLATE0 = X_DIFF1 - P["fan_plate_t"]           # 395
X_FAN1 = X_DIFF1 + P["fan_depth"]                   # 438
FLOOR_TOP = -P["ts_half"]                           # -50
FLOOR_BOT = -P["ts_half"] - P["wall"]               # -53
BAY_BOT = FLOOR_BOT - P["bay_depth"]                # -133
P["table_z"] = BAY_BOT                              # table level follows the bay depth


# ================================================================ helpers
def sq(half):
    return [(-half, -half), (half, -half), (half, half), (-half, half)]


def sq3(x, half):
    """Square wire in the plane x = const (points as 3-D tuples)."""
    return [(x, -half, -half), (x, half, -half), (x, half, half), (x, -half, half)]


def rounded_square3(x, half, r, n=64):
    """Rounded square (corner radius r) in the plane x = const, n points.
    r = half gives a circle. Used for the square-to-round diffuser loft."""
    pts = []
    r = min(max(r, 1e-6), half)
    for i in range(n):
        a = 2 * math.pi * i / n
        # superellipse-like blend: polygon vertices on a rounded square
        cx = math.copysign(half - r, math.cos(a)) if abs(math.cos(a)) > 1e-9 else 0.0
        cy = math.copysign(half - r, math.sin(a)) if abs(math.sin(a)) > 1e-9 else 0.0
        pts.append((x, cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def contraction_half(x):
    """Half width of the contraction at station x (5th-order polynomial)."""
    xi = (x - X_C_IN) / P["contraction_len"]
    xi = min(max(xi, 0.0), 1.0)
    f = 6 * xi ** 5 - 15 * xi ** 4 + 10 * xi ** 3
    return P["sc_half"] - (P["sc_half"] - P["ts_half"]) * f


def flange_hole_points(half):
    """Bolt pattern for a square flange of inner half width `half`."""
    p = half + P["wall"] + P["flange_w"] / 2
    pts = [(sx * p, sz * p) for sx in (-1, 1) for sz in (-1, 1)]
    if half >= 90:   # big flanges (settling chamber, bellmouth) get mid holes
        pts += [(sx * p, sz * p / 2) for sx in (-1, 1) for sz in (-1, 1)]
        pts += [(sx * p / 2, sz * p) for sx in (-1, 1) for sz in (-1, 1)]
    return pts


def flange(x0, half, holes=True, t=None, extra_hole_d=None):
    """Square flange plate from x0 to x0+t with the duct opening."""
    t = P["flange_t"] if t is None else t
    outer = half + P["wall"] + P["flange_w"]
    s = K.box(t, 2 * outer, 2 * outer, (x0, -outer, -outer))
    s = K.cut(s, K.box(t + 2, 2 * half, 2 * half, (x0 - 1, -half, -half)))
    if holes:
        d = extra_hole_d or P["bolt_d"]
        for (y, z) in flange_hole_points(half):
            s = K.cut(s, K.cyl(d / 2, t + 2, (x0 - 1, y, z), "x"))
    return s


def square_duct(x0, x1, half, wall=None):
    wall = P["wall"] if wall is None else wall
    o = half + wall
    s = K.box(x1 - x0, 2 * o, 2 * o, (x0, -o, -o))
    return K.cut(s, K.box(x1 - x0 + 2, 2 * half, 2 * half, (x0 - 1, -half, -half)))


def naca4(code, chord, n=60, te_min=0.8):
    """NACA 4-digit airfoil polygon (x, z) with a blunt trailing edge of
    te_min total thickness. Chord along +x from 0 to chord."""
    m = int(code[0]) / 100.0
    pp = int(code[1]) / 10.0
    t = int(code[2:]) / 100.0
    up, lo = [], []
    for i in range(n + 1):
        b = math.pi * i / n
        xc = 0.5 * (1 - math.cos(b))       # cosine spacing
        yt = 5 * t * (0.2969 * math.sqrt(xc) - 0.1260 * xc - 0.3516 * xc ** 2
                      + 0.2843 * xc ** 3 - 0.1036 * xc ** 4)
        yt += (te_min / 2 / chord) * xc ** 2    # blunt TE ramp
        if m > 0 and pp > 0:
            if xc < pp:
                yc = m / pp ** 2 * (2 * pp * xc - xc ** 2)
                dyc = 2 * m / pp ** 2 * (pp - xc)
            else:
                yc = m / (1 - pp) ** 2 * ((1 - 2 * pp) + 2 * pp * xc - xc ** 2)
                dyc = 2 * m / (1 - pp) ** 2 * (pp - xc)
        else:
            yc, dyc = 0.0, 0.0
        th = math.atan(dyc)
        up.append(((xc - yt * math.sin(th)) * chord, (yc + yt * math.cos(th)) * chord))
        lo.append(((xc + yt * math.sin(th)) * chord, (yc - yt * math.cos(th)) * chord))
    pts = up[::-1] + lo[1:]          # TE upper -> LE -> TE lower (closed by prism)
    return pts


def symmetric_strut_section(chord, t):
    """Thick symmetric section for the strut: NACA 00xx scaled to thickness t."""
    pts = naca4("0030", chord, n=40, te_min=0.0)
    scale = t / (0.30 * chord)
    return [(x, z * scale) for x, z in pts]


def tongue(x, z0, up=True, y=0.0):
    """Rectangular tongue (w x t) of height tongue_h, starting at z0."""
    w, t, h = P["tongue_w"], P["tongue_t"], P["tongue_h"]
    z = z0 if up else z0 - h
    return K.box(w, t, h, (x - w / 2, y - t / 2, z))


def socket_cut(x, z0, up=True, y=0.0, extra=0.0):
    w = P["tongue_w"] + 2 * P["tongue_clear"]
    t = P["tongue_t"] + 2 * P["tongue_clear"]
    h = P["tongue_h"] + extra
    z = z0 if up else z0 - h
    return K.box(w, t, h, (x - w / 2, y - t / 2, z))


def pin_hole(x, z, y0=-20, length=40):
    return K.cyl(P["pin_d"] / 2, length, (x, y0, z), "y")


# ================================================================ parts
PARTS = {}   # name -> dict(solid, print_rot, note, reference)


CONFIGS = {   # which test configuration a part belongs to (for the interference check)
    "strut_long": {"wing"}, "wing_naca0012": {"wing"}, "wing_naca4412": {"wing_b"},
    "wing_flat_plate": {"wing_c"}, "probe_plug": {"wing", "wing_b", "wing_c", "car"},
    "zero_gauge": {"wing", "wing_b", "wing_c"},
    "strut_short": {"car"}, "car_tray": {"car"}, "ground_board": {"car"}, "ref_car": {"car"},
    "pitot_wand": {"cal"},
}


def add(name, solid, print_rot=None, note="", reference=False, qty=1, material="PETG"):
    PARTS[name] = {"solid": solid, "print_rot": print_rot or [], "note": note,
                   "reference": reference, "qty": qty, "material": material,
                   "configs": sorted(CONFIGS.get(name, {"all"}))}


def part_bellmouth_quarter():
    R, T, OH = P["bell_r"], P["bell_t"], P["bell_outer_half"]
    h0 = P["sc_half"]
    # Outer plate
    s = K.box(T, 2 * OH, 2 * OH, (X_BELL, -OH, -OH))
    # Inner lip surface as a loft of squares following a quarter circle
    secs = []
    n = 14
    for i in range(n + 1):
        tt = R * i / n                      # distance upstream of the chamber plane
        xx = X_SC_IN - tt
        half = h0 + R - math.sqrt(max(R * R - tt * tt, 0.0))
        secs.append(sq3(xx, half))
    # extend the loft a little past both faces so the cut is clean
    secs.insert(0, sq3(X_SC_IN + 1.0, h0))
    secs.append(sq3(X_BELL - 1.0, h0 + R))
    lip = K.loft(secs, ruled=False)
    s = K.cut(s, lip)
    for (y, z) in flange_hole_points(h0):
        s = K.cut(s, K.cyl(P["bolt_d"] / 2, T + 2, (X_BELL - 1, y, z), "x"))
    # Quarter: y>0, z>0 (the other three are the same part, rotated)
    q = K.common(s, K.box(T + 2, OH + 1, OH + 1, (X_BELL - 1, 0, 0)))
    return q


def part_settling_chamber():
    h = P["sc_half"]
    s = square_duct(X_SC_IN, X_C_IN, h)
    s = K.fuse(s, flange(X_SC_IN, h))
    s = K.fuse(s, flange(X_C_IN - P["flange_t"], h))
    # retaining lip at the downstream end
    lip = K.box(P["lip_t"], 2 * h, 2 * h, (X_C_IN - P["lip_t"], -h, -h))
    lip = K.cut(lip, K.box(P["lip_t"] + 2, 2 * (h - P["lip_w"]), 2 * (h - P["lip_w"]),
                          (X_C_IN - P["lip_t"] - 1, -(h - P["lip_w"]), -(h - P["lip_w"]))))
    s = K.fuse(s, lip)
    return s


def part_honeycomb():
    h = P["sc_half"] - P["stack_clear"]            # 99.5
    a, w, L = P["hc_cell"], P["hc_wall"], P["hc_len"]
    pitch = a + w
    R = a / math.sqrt(3)                            # circumradius of the cell
    inner_lim = h - P["hc_rim"]
    holes = []
    rows = int(2 * h / (pitch * math.sqrt(3) / 2)) + 2
    cols = int(2 * h / pitch) + 2
    for i in range(-rows, rows + 1):
        cz = i * pitch * math.sqrt(3) / 2
        for j in range(-cols, cols + 1):
            cy = j * pitch + (pitch / 2 if i % 2 else 0.0)
            if abs(cy) + R > inner_lim or abs(cz) + R > inner_lim:
                continue
            hexpts = [(cy + R * math.cos(math.pi / 6 + k * math.pi / 3),
                       cz + R * math.sin(math.pi / 6 + k * math.pi / 3)) for k in range(6)]
            holes.append(hexpts)
    x0 = X_SC_IN + 28.0 + P["lip_t"] * 0          # position in the stack (see docs)
    # stack from downstream: lip 3 | screen 2.5 | spacer 12 | screen 2.5 | spacer 12 | honeycomb 40 | spacer 28
    x_hc0 = X_C_IN - P["lip_t"] - 2 * P["screen_t"] - 2 * 12.0 - L
    s = K.prism(sq(h), L, plane="yz", offset=x_hc0, holes=holes)
    return s, len(holes), x_hc0


def part_spacer(length, x0):
    h = P["sc_half"] - P["stack_clear"]
    s = K.box(length, 2 * h, 2 * h, (x0, -h, -h))
    hi = h - P["spacer_wall"]
    return K.cut(s, K.box(length + 2, 2 * hi, 2 * hi, (x0 - 1, -hi, -hi)))


def part_screen_frame(x0):
    h = P["sc_half"] - P["stack_clear"]
    s = K.box(P["screen_t"], 2 * h, 2 * h, (x0, -h, -h))
    hi = h - P["screen_frame_w"]
    return K.cut(s, K.box(P["screen_t"] + 2, 2 * hi, 2 * hi, (x0 - 1, -hi, -hi)))


def part_contraction(x0, x1):
    n = 24
    inner, outer = [], []
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n
        hh = contraction_half(x)
        inner.append(sq3(x, hh))
        outer.append(sq3(x, hh + P["wall"]))
    # extend inner loft past the ends for a clean cut
    inner.insert(0, sq3(x0 - 1, contraction_half(x0)))
    inner.append(sq3(x1 + 1, contraction_half(x1)))
    s = K.cut(K.loft(outer), K.loft(inner))
    s = K.fuse(s, flange(x0, contraction_half(x0)))
    s = K.fuse(s, flange(x1 - P["flange_t"], contraction_half(x1)))
    # re-cut the opening in the flanges exactly at the local half width
    s = K.cut(s, K.loft(inner))
    return s


def add_tap(s, x, y, z, axis):
    return K.cut(s, K.cyl(P["tap_d"] / 2, 20, (x, y, z), axis))


def part_ts1():
    h = P["ts_half"]
    s = square_duct(X_TS0, X_TS1, h)
    s = K.fuse(s, flange(X_TS0, h))
    s = K.fuse(s, flange(X_TS1 - P["flange_t"], h))
    # static pressure ring: 3 taps at x = 20 (top and both sides)
    s = add_tap(s, 20.0, 0.0, h - 10, "z")
    s = add_tap(s, 20.0, -h - 10, 0.0, "y")
    s = add_tap(s, 20.0, h - 10, 0.0, "y")
    return s


def part_ts2():
    h = P["ts_half"]
    s = square_duct(X_TS1, X_TS2, h)
    s = K.fuse(s, flange(X_TS1, h))
    s = K.fuse(s, flange(X_TS2 - P["flange_t"], h))
    # windows: raised boss on the outside, opening, recess for the sheet, magnet pockets
    wx0, wx1, wz = P["window_x0"], P["window_x1"], P["window_half_z"]
    m, rec = P["window_margin"], P["window_recess"]
    bw, bt = P["window_boss_w"], P["window_boss"]
    yo = h + P["wall"] + bt                       # outer face of the boss
    for sgn in (-1, 1):
        boss = K.box(wx1 - wx0 + 2 * bw, bt, 2 * (wz + bw),
                     (wx0 - bw, (yo - bt) if sgn > 0 else -yo, -wz - bw))
        s = K.fuse(s, boss)
    s = K.cut(s, K.box(wx1 - wx0, 2 * h + 20, 2 * wz, (wx0, -h - 10, -wz)))
    md, mt = P["magnet_d"] + 0.3, P["magnet_t"] + 0.2
    for sgn in (-1, 1):
        y_rec = (yo - rec) if sgn > 0 else -yo
        s = K.cut(s, K.box(wx1 - wx0 + 2 * m, rec, 2 * (wz + m), (wx0 - m, y_rec, -wz - m)))
        y_mag = (yo - mt) if sgn > 0 else -yo
        for px in (wx0 - m - 6, wx1 + m + 6):
            for pz in (-wz - m + 4, wz + m - 4):
                s = K.cut(s, K.cyl(md / 2, mt, (px, y_mag, pz), "y"))
    # floor slot for the strut
    s = K.cut(s, K.box(2 * P["slot_x_half"], 2 * P["slot_y_half"], 20,
                       (P["model_x"] - P["slot_x_half"], -P["slot_y_half"], FLOOR_BOT - 10)))
    # bay bolt holes through the floor
    for bx in P["bay_bolt_x"]:
        for by in (-P["bay_bolt_y"], P["bay_bolt_y"]):
            s = K.cut(s, K.cyl(P["bolt_d"] / 2, 20, (bx, by, FLOOR_BOT - 10), "z"))
    # ground board peg holes
    for gx in P["gb_peg_x"]:
        for gy in (-P["gb_peg_y"], P["gb_peg_y"]):
            s = K.cut(s, K.cyl(P["gb_peg_hole_d"] / 2, 20, (gx, gy, FLOOR_BOT - 10), "z"))
    # probe access hole on the top wall at the model station, and a static tap
    s = K.cut(s, K.cyl(P["probe_hole_d"] / 2, 20, (P["model_x"], 0, h - 10), "z"))
    s = add_tap(s, P["model_x"], 25.0, h - 10, "z")
    return s


def part_window_clip():
    """Magnet frame that holds the window sheet in the recess."""
    wx0, wx1, wz = P["window_x0"], P["window_x1"], P["window_half_z"]
    m = P["window_margin"]
    yo = P["ts_half"] + P["wall"] + P["window_boss"]
    t = 3.0
    ox0, ox1 = wx0 - m - 9, wx1 + m + 9
    s = K.box(ox1 - ox0, t, 2 * (wz + m + 9), (ox0, yo, -wz - m - 9))
    s = K.cut(s, K.box(wx1 - wx0 + 4, t + 2, 2 * (wz + 2), (wx0 - 2, yo - 1, -wz - 2)))
    md, mt = P["magnet_d"] + 0.3, P["magnet_t"] + 0.2
    for px in (wx0 - m - 6, wx1 + m + 6):
        for pz in (-wz - m + 4, wz + m - 4):
            s = K.cut(s, K.cyl(md / 2, mt, (px, yo, pz), "y"))
    return s


def part_diffuser():
    h = P["ts_half"]
    n = 20
    inner, outer = [], []
    rf = P["fan_bore"] / 2
    for i in range(n + 1):
        f = i / n
        x = X_TS2 + P["diff_len"] * f
        half = h + (rf - h) * f
        r = half * (0.02 + 0.98 * f)      # corner radius grows to a full circle
        inner.append(rounded_square3(x, half, r))
        outer.append(rounded_square3(x, half + P["wall"], r + P["wall"] * f * 0 + (P["wall"] if f > 0.99 else r * 0)))
    # outer: simple approach, offset each section by wall thickness radially
    outer = []
    for i in range(n + 1):
        f = i / n
        x = X_TS2 + P["diff_len"] * f
        half = h + (rf - h) * f + P["wall"]
        r = (half - P["wall"]) * (0.02 + 0.98 * f) + P["wall"]
        outer.append(rounded_square3(x, half, min(r, half)))
    inner_ext = [rounded_square3(X_TS2 - 1, h, h * 0.02)] + inner + \
                [rounded_square3(X_DIFF1 + 1, rf, rf)]
    s = K.cut(K.loft(outer), K.loft(inner_ext))
    s = K.fuse(s, flange(X_TS2, h))
    # fan plate with nut traps on the upstream face
    fp = P["fan_plate_half"]
    plate = K.box(P["fan_plate_t"], 2 * fp, 2 * fp, (X_FAN_PLATE0, -fp, -fp))
    plate = K.cut(plate, K.cyl(rf, P["fan_plate_t"] + 2, (X_FAN_PLATE0 - 1, 0, 0), "x"))
    hp = P["fan_hole_pitch"] / 2
    for sy in (-1, 1):
        for sz in (-1, 1):
            plate = K.cut(plate, K.cyl(P["fan_bolt_d"] / 2, 20, (X_FAN_PLATE0 - 10, sy * hp, sz * hp), "x"))
            hexnut = [(sy * hp + 4.0 * math.cos(a), sz * hp + 4.0 * math.sin(a))
                      for a in [math.pi / 6 + k * math.pi / 3 for k in range(6)]]
            plate = K.cut(plate, K.prism(hexnut, 3.2, plane="yz", offset=X_FAN_PLATE0 - 0.1))
    s = K.fuse(s, plate)
    s = K.cut(s, K.loft(inner_ext))
    return s


def part_fan_guard():
    fp, rf = P["fan_plate_half"], P["fan_bore"] / 2
    t = P["guard_t"]
    x0 = X_FAN1
    s = K.box(t, 2 * fp, 2 * fp, (x0, -fp, -fp))
    s = K.cut(s, K.cyl(rf, t + 2, (x0 - 1, 0, 0), "x"))
    hp = P["fan_hole_pitch"] / 2
    for sy in (-1, 1):
        for sz in (-1, 1):
            s = K.cut(s, K.cyl(P["fan_bolt_d"] / 2, 20, (x0 - 10, sy * hp, sz * hp), "x"))
    # grille: rings and spokes, 3 mm thick, flush with the upstream face
    gt = 3.0
    bar = P["guard_bar"]
    hub = K.cyl(14.0, gt, (x0, 0, 0), "x")
    grid = hub
    for i in range(1, P["guard_rings"] + 1):
        r = 14.0 + (rf + 1.0 - 14.0) * i / P["guard_rings"]
        ring = K.cut(K.cyl(r + bar / 2, gt, (x0, 0, 0), "x"), K.cyl(r - bar / 2, gt + 2, (x0 - 1, 0, 0), "x"))
        grid = K.fuse(grid, ring)
    for k in range(P["guard_spokes"]):
        a = 2 * math.pi * k / P["guard_spokes"]
        spoke = K.box(gt, bar, rf + 2, (x0, -bar / 2, 0))
        spoke = K.rotate(spoke, (x0, 0, 0), "x", math.degrees(a))
        grid = K.fuse(grid, spoke)
    grid = K.common(grid, K.cyl(rf + 1.5, gt, (x0, 0, 0), "x"))
    return K.fuse(s, grid)


def part_bay():
    x0, x1 = P["bay_x0"], P["bay_x1"]
    hy, d, bt = P["bay_half_y"], P["bay_depth"], P["bay_base_t"]
    z0 = FLOOR_BOT - d
    s = K.box(x1 - x0, 2 * hy, d, (x0, -hy, z0))
    wi = P["wall"]
    s = K.cut(s, K.box(x1 - x0 - 2 * wi, 2 * (hy - wi), d, (x0 + wi, -(hy - wi), z0 + bt)))
    # top lips with bolt holes
    lw = P["bay_lip_w"]
    for sgn in (-1, 1):
        yl = sgn * (hy - wi) - (lw if sgn > 0 else 0)
        lip = K.box(x1 - x0 - 2 * wi, lw, 4.0, (x0 + wi, yl, FLOOR_BOT - 4.0))
        s = K.fuse(s, lip)
    for bx in P["bay_bolt_x"]:
        for by in (-P["bay_bolt_y"], P["bay_bolt_y"]):
            s = K.cut(s, K.cyl(P["bolt_d"] / 2, 20, (bx, by, FLOOR_BOT - 10), "z"))
    # cable hole on the -y wall
    s = K.cut(s, K.cyl(5.0, 20, (140.0, -hy - 10, z0 + 25), "y"))
    # ---- balance ground-side features fused to the base
    base_top = z0 + bt
    # drag cell post (downstream of the drag cell)
    s = K.fuse(s, K.box(DRAG_POST[1] - DRAG_POST[0], DRAG_Y[1] - DRAG_Y[0], DRAG_POST_TOP - base_top,
                        (DRAG_POST[0], DRAG_Y[0], base_top)))
    for zo in P["cell_holes"]:
        zz = DRAG_Z0 + zo
        s = K.cut(s, K.cyl(P["cell_hole_d"] / 2 + 0.2, 20, (DRAG_POST[0] - 1, DRAG_CELL_Y, zz), "x"))
    # overload stop columns and fingers (on the -y side of the platform)
    g = P["stop_gap"]
    for (cx0, cx1, fx0, fx1) in ((PLATE_X[0] - g - 12, PLATE_X[0] - g, PLATE_X[0], PLATE_X[0] + 4),
                                 (PLATE_X[1] + g, PLATE_X[1] + g + 12, PLATE_X[1] - 4, PLATE_X[1])):
        col = K.box(cx1 - cx0, 10.0, (PLATE_Z[1] + 4.0) - base_top, (cx0, STOP_Y[0], base_top))
        s = K.fuse(s, col)
        over = K.box((fx1 - cx0) if cx0 < fx0 else (cx1 - fx0), STOP_Y[1] - STOP_Y[0] + 8, 3.4,
                     (min(cx0, fx0), STOP_Y[0], PLATE_Z[1] + g))
        under = K.box((fx1 - cx0) if cx0 < fx0 else (cx1 - fx0), STOP_Y[1] - STOP_Y[0] + 8, 3.4,
                      (min(cx0, fx0), STOP_Y[0], PLATE_Z[0] - g - 3.4))
        s = K.fuse(s, over)
        s = K.fuse(s, under)
    return s


# ---- balance geometry (shared between parts) --------------------------------
CELL_L, CELL_W, CELL_T = P["cell_L"], P["cell_w"], P["cell_t"]
MX = P["model_x"]
DRUM_Z = P["drum_z"]                               # -65
PLATE_Z = (DRUM_Z - 5.0, DRUM_Z - 1.0)             # -70 .. -66
PLATE_X = (168.0, 214.0)
PLATE_Y = (-28.0, 13.0)
STOP_Y = (-34.0, -20.0)
LIFT_X = 205.0
LIFT_TOP = DRUM_Z - P["drum_r"] - 2.0              # -77
LIFT_Y = (-25.0, -25.0 + CELL_L)                   # -25 .. 20  (free end at -25)
LIFT_FREE_HOLES = [LIFT_Y[0] + h for h in P["cell_holes"]]
LIFT_FIXED_HOLES = [LIFT_Y[1] - h for h in P["cell_holes"]]
FOOT_Z = (LIFT_TOP, PLATE_Z[0])
DRAG_X = 217.0
DRAG_CELL_Y = 27.0
DRAG_Y = (21.0, 33.0)
DRAG_TOP = LIFT_TOP
DRAG_Z0 = DRAG_TOP - CELL_L                        # -122
DRAG_POST = (DRAG_X + CELL_T / 2, DRAG_X + CELL_T / 2 + 9.0)
DRAG_POST_TOP = DRAG_Z0 + 13.0
BRACKET_X = (DRAG_X + CELL_T / 2, DRAG_X + CELL_T / 2 + 10.0)
BRACKET_Z = (DRAG_TOP - 13.0, DRAG_TOP + 2.0)
ARM_Z = (LIFT_TOP, LIFT_TOP + 4.0)
ARM_X = (LIFT_X - CELL_W / 2 - 1.0, BRACKET_X[1])
ARM_Y = (LIFT_Y[1] - 11.0, DRAG_Y[1])
SERVO_X0 = MX - P["servo_shaft_from_end"]          # 179
SERVO_Y0 = P["drum_half_w"] + P["servo_horn_gap"]  # 8
SERVO_Z = (DRUM_Z - P["servo_W"] / 2, DRUM_Z + P["servo_W"] / 2)
HANGER_Y = (SERVO_Y0 + P["servo_flange_from_top"] + P["servo_flange_t"],
            SERVO_Y0 + P["servo_flange_from_top"] + P["servo_flange_t"] + 3.0)
HANGER_Z = (DRUM_Z - 7.0, DRUM_Z + 9.0)
HANGER_X = (170.0, 210.0)
TAB_HOLE_X = (SERVO_X0 - 2.5, SERVO_X0 + P["servo_L"] + 2.5)
BARS_X = ((PLATE_X[0], SERVO_X0 - P["servo_tab"] - 1.0),
          (SERVO_X0 + P["servo_L"] + P["servo_tab"] + 0.5, PLATE_X[1]))
STUB_Y = (-P["drum_half_w"] - P["stub_len"], -P["drum_half_w"])
BUSH_Y = (-13.0, -7.0)
SENSOR_POST_Y = (-15.0, -13.0)
AS5600_Y = (SENSOR_POST_Y[0] - 1.6, SENSOR_POST_Y[0])


def part_platform():
    """Metric platform: plate, lift-cell foot, servo hanger, drum bushing, sensor post."""
    z0, z1 = PLATE_Z
    s = K.box(PLATE_X[1] - PLATE_X[0], PLATE_Y[1] - PLATE_Y[0], z1 - z0, (PLATE_X[0], PLATE_Y[0], z0))
    s = K.cut(s, K.box(2 * (P["drum_r"] + 1.0), 2 * (P["drum_half_w"] + 1.0), 20,
                       (MX - P["drum_r"] - 1.0, -P["drum_half_w"] - 1.0, z0 - 10)))
    s = K.cut(s, K.box(P["servo_L"] + 2 * P["servo_tab"] + 2.0, 20.0, 20,
                       (SERVO_X0 - P["servo_tab"] - 1.0, SERVO_Y0 - 1.0, z0 - 10)))
    s = K.cut(s, K.box(26.0, 2.6, 20, (MX - 13.0, AS5600_Y[0] - 0.5, z0 - 10)))
    s = K.fuse(s, K.box(CELL_W + 2.0, 11.5, FOOT_Z[1] - FOOT_Z[0],
                        (LIFT_X - CELL_W / 2 - 1.0, LIFT_Y[0], FOOT_Z[0])))
    for yh in LIFT_FREE_HOLES:
        s = K.cut(s, K.cyl(P["cell_hole_d"] / 2 + 0.1, 30, (LIFT_X, yh, FOOT_Z[0] - 5), "z"))
    for (bx0, bx1) in BARS_X:
        s = K.fuse(s, K.box(bx1 - bx0, HANGER_Y[1] - PLATE_Y[1], z1 - z0, (bx0, PLATE_Y[1], z0)))
    hang = K.box(HANGER_X[1] - HANGER_X[0], HANGER_Y[1] - HANGER_Y[0], HANGER_Z[1] - HANGER_Z[0],
                 (HANGER_X[0], HANGER_Y[0], HANGER_Z[0]))
    hang = K.cut(hang, K.box(P["servo_L"] + 1.0, 10, P["servo_W"] + 1.0,
                             (SERVO_X0 - 0.5, HANGER_Y[0] - 1, SERVO_Z[0] - 0.5)))
    for tx in TAB_HOLE_X:
        hang = K.cut(hang, K.cyl(P["servo_tab_hole_d"] / 2, 10, (tx, HANGER_Y[0] - 1, DRUM_Z), "y"))
    s = K.fuse(s, hang)
    bush = K.box(14.0, BUSH_Y[1] - BUSH_Y[0], 16.0, (MX - 7.0, BUSH_Y[0], DRUM_Z - 7.0))
    s = K.fuse(s, bush)
    s = K.cut(s, K.cyl(P["stub_d"] / 2 + P["stub_hole_clear"], 10, (MX, BUSH_Y[0] - 1, DRUM_Z), "y"))
    post = K.box(26.0, SENSOR_POST_Y[1] - SENSOR_POST_Y[0], 24.0, (MX - 13.0, SENSOR_POST_Y[0], DRUM_Z - 12.0))
    for hx in (MX - 7.5, MX + 7.5):
        post = K.cut(post, K.cyl(1.0, 10, (hx, SENSOR_POST_Y[0] - 1, DRUM_Z), "y"))
    s = K.fuse(s, post)
    return s


def part_bracket():
    """Drag-cell to lift-cell bracket (metric for drag, ground for lift)."""
    s = K.box(BRACKET_X[1] - BRACKET_X[0], DRAG_Y[1] - DRAG_Y[0], BRACKET_Z[1] - BRACKET_Z[0],
              (BRACKET_X[0], DRAG_Y[0], BRACKET_Z[0]))
    for zo in P["cell_holes"]:
        zz = DRAG_TOP - zo
        s = K.cut(s, K.cyl(P["cell_hole_d"] / 2 + 0.1, 30, (BRACKET_X[0] - 1, DRAG_CELL_Y, zz), "x"))
    arm = K.box(ARM_X[1] - ARM_X[0], ARM_Y[1] - ARM_Y[0], ARM_Z[1] - ARM_Z[0], (ARM_X[0], ARM_Y[0], ARM_Z[0]))
    s = K.fuse(s, arm)
    for yh in LIFT_FIXED_HOLES:
        s = K.cut(s, K.cyl(P["cell_hole_d"] / 2 + 0.1, 30, (LIFT_X, yh, ARM_Z[0] - 5), "z"))
    return s


def strut_body(z0, z1, x=MX):
    sec = symmetric_strut_section(P["strut_chord"], P["strut_t"])
    pts = [(x - P["strut_chord"] / 2 + sx, sz) for sx, sz in sec]
    # prism in the xy plane? The section is in x-y (chord x, thickness y), extruded along z.
    return K.prism(pts, z1 - z0, plane="xy", offset=z0)


def part_drum():
    r, hw = P["drum_r"], P["drum_half_w"]
    s = K.cyl(r, 2 * hw, (MX, -hw, DRUM_Z), "y")
    # strut socket on top (tongue goes down into the drum)
    top = DRUM_Z + r
    s = K.cut(s, socket_cut(MX, top, up=False, extra=0.0))
    s = K.cut(s, pin_hole(MX, top - P["tongue_h"] / 2))
    # horn pocket on the +y face: a slot 5 wide x 22 long x 1.8 deep, plus screw hole
    s = K.cut(s, K.box(22.0, 1.8, 5.0, (MX - 11.0, hw - 1.8, DRUM_Z - 2.5)))
    s = K.cut(s, K.cyl(1.6, 2 * hw + 2, (MX, -hw - 1, DRUM_Z), "y"))   # M3 horn screw clearance
    # stub axle on the -y face with a magnet pocket in its end
    stub = K.cyl(P["stub_d"] / 2, P["stub_len"] + 0.01, (MX, STUB_Y[0], DRUM_Z), "y")
    s = K.fuse(s, stub)
    md, mt = P["magnet_d"] + 0.3, P["magnet_t"] + 0.2
    s = K.cut(s, K.cyl(md / 2, mt, (MX, STUB_Y[0] - 0.01, DRUM_Z), "y"))
    return s


def part_strut(long: bool):
    top = DRUM_Z + P["drum_r"]                     # -53
    z_top = (P["wing_z"] - 3.0 - P["tongue_h"]) if long else (P["car_tray_z"] - 2.0 - P["tongue_h"])
    body = strut_body(top, z_top)
    s = K.fuse(body, tongue(MX, top, up=False))        # root tongue into the drum
    s = K.fuse(s, tongue(MX, z_top, up=True))          # top tongue into the model
    s = K.cut(s, pin_hole(MX, top - P["tongue_h"] / 2))
    s = K.cut(s, pin_hole(MX, z_top + P["tongue_h"] / 2))
    return s, z_top


def pylon(z_tongue0, z_join, x=MX):
    """Socket block that fits over a strut tongue, from z_tongue0 up to z_join."""
    t = P["pylon_t"]
    w = P["strut_chord"]
    h = z_join - (z_tongue0 + 0.5)
    s = K.box(w, t, h, (x - w / 2, -t / 2, z_tongue0 + 0.5))
    s = K.cut(s, socket_cut(x, z_tongue0 + 0.3, up=True, extra=0.5))
    s = K.cut(s, pin_hole(x, z_tongue0 + P["tongue_h"] / 2))
    return s


def part_wing(code, name):
    c, b = P["wing_chord"], P["wing_span"]
    pts = naca4(code, c, te_min=P["wing_te_min"]) if code != "plate" else None
    x_le = MX - 0.25 * c
    zc = P["wing_z"]
    if pts is None:  # flat plate 2 mm with rounded edges approximated by a polygon
        t = 2.0
        n = 12
        le = [(t / 2 - t / 2 * math.cos(a), t / 2 * math.sin(a)) for a in
              [math.pi / 2 + math.pi * i / n for i in range(n + 1)]]
        pts = [(c, t / 2)] + le + [(c, -t / 2)]
    pts3 = [(x_le + px, pz + zc) for px, pz in pts]
    wing = K.prism(pts3, b, plane="xz", offset=-b / 2)
    tongue_z0 = zc - 3.0 - P["tongue_h"]
    py = pylon(tongue_z0, zc + 1.0)
    s = K.fuse(wing, py)
    return s


def part_car_tray():
    L, W, t = P["car_len"], P["car_w"], P["tray_t"]
    z0 = P["car_tray_z"]
    s = K.box(L, W, t, (MX - L / 2, -W / 2, z0))
    # wheel cut-outs
    for dx in (-P["car_wheelbase"] / 2, P["car_wheelbase"] / 2):
        for dy in (-P["car_track"] / 2, P["car_track"] / 2):
            s = K.cut(s, K.box(P["car_wheel_d"] + 2, 5.0, t + 2, (MX + dx - (P["car_wheel_d"] + 2) / 2, dy - 2.5, z0 - 1)))
    # magnet pockets (optional, for steel chassis cars)
    md, mt = P["magnet_d"] + 0.3, P["magnet_t"] + 0.2
    for dx in (-12.0, 12.0):
        s = K.cut(s, K.cyl(md / 2, mt, (MX + dx, 0, z0 + t - mt), "z"))
    # side locating bumps
    for sy in (-1, 1):
        for dx in (-25.0, 25.0):
            s = K.fuse(s, K.box(6.0, 1.5, 3.0, (MX + dx - 3.0, sy * (W / 2) - (1.5 if sy > 0 else 0), z0 + t)))
    # neck with the socket for the short strut
    tongue_top = z0 - 2.0
    s = K.fuse(s, pylon(tongue_top - P["tongue_h"], z0 + 0.5))
    return s


def part_ground_board():
    x0, x1 = P["ground_board_x"]
    top, t = P["ground_board_top"], P["ground_board_t"]
    hy = P["ts_half"] - 0.5
    s = K.box(x1 - x0, 2 * hy, t, (x0, -hy, top - t))
    # leading and trailing edge bevels on the underside
    bv = P["ground_board_bevel"]
    for (xa, xb) in ((x0, x0 + bv), (x1 - bv, x1)):
        tri = [(xa, top - t), (xb, top - t), (xb if xa == x0 else xa, top - 0.8)] if xa == x0 else \
              [(xa, top - 0.8), (xb, top - t), (xa, top - t)]
        if xa == x0:
            tri = [(x0, top - 0.8), (x0, top - t), (x0 + bv, top - t)]
        else:
            tri = [(x1, top - 0.8), (x1 - bv, top - t), (x1, top - t)]
        s = K.cut(s, K.prism(tri, 2 * hy + 2, plane="xz", offset=-hy - 1))
    # slot for the strut neck
    sx, sy = P["ground_board_slot"]
    s = K.cut(s, K.box(sx, sy, t + 2, (MX - sx / 2, -sy / 2, top - t - 1)))
    # pegs down to the floor
    for gx in P["gb_peg_x"]:
        for gy in (-P["gb_peg_y"], P["gb_peg_y"]):
            s = K.fuse(s, K.cyl(P["gb_peg_d"] / 2, (top - t) - FLOOR_TOP + 0.01, (gx, gy, FLOOR_TOP), "z"))
            s = K.fuse(s, K.cyl(3.0, (top - t) - FLOOR_TOP - 3.0, (gx, gy, FLOOR_TOP + 3.0), "z"))
    return s


def part_stand(x0, width_outer, bottom_z, name):
    """Arch stand: 6 mm legs, 5 mm top bar, two cheeks that grip the duct sides."""
    L = 40.0
    h = bottom_z - P["table_z"]
    half = width_outer / 2 + 6.0
    s = K.box(L, 2 * half, h, (x0, -half, P["table_z"]))
    s = K.cut(s, K.box(L + 2, 2 * half - 12.0, h - 5.0, (x0 - 1, -half + 6.0, P["table_z"] - 1)))
    for sgn in (-1, 1):
        cheek = K.box(L, 6.0, 12.0, (x0, sgn * (width_outer / 2) - (0 if sgn > 0 else 6.0), bottom_z))
        s = K.fuse(s, cheek)
    return s


def part_fan_stand():
    """Arch stand under the fan plate with four small fences that locate the plate."""
    fp = P["fan_plate_half"]
    bottom = -fp
    L = 30.0
    x0 = X_FAN_PLATE0 - (L - P["fan_plate_t"]) / 2
    h = bottom - P["table_z"]
    half = fp + 8.0
    s = K.box(L, 2 * half, h, (x0, -half, P["table_z"]))
    s = K.cut(s, K.box(L + 2, 2 * half - 16.0, h - 5.0, (x0 - 1, -half + 8.0, P["table_z"] - 1)))
    for sy in (-1, 1):
        for (fx0, fx1) in ((X_FAN_PLATE0 - 2.5, X_FAN_PLATE0 - 0.3), (X_DIFF1 + 0.3, X_DIFF1 + 2.5)):
            y0 = fp if sy > 0 else -fp - 8.0
            s = K.fuse(s, K.box(fx1 - fx0, 8.0, 8.0, (fx0, y0, bottom)))
    return s


def part_tap_barb():
    s = K.cyl(2.0, 12.0, (0, 0, 0), "z")
    s = K.fuse(s, K.cyl(4.0, 1.5, (0, 0, 0), "z"))
    s = K.fuse(s, K.cyl(2.4, 1.0, (0, 0, 10.0), "z"))    # barb ridge
    s = K.cut(s, K.cyl(0.75, 14.0, (0, 0, -1), "z"))
    return s


def part_pitot_wand():
    # vertical leg from above the top wall down to the model centre, head facing upstream
    top = P["ts_half"] + P["wall"] + 25.0
    s = K.cyl(2.3, top - P["wing_z"] + 2.3, (MX, 0, P["wing_z"] - 2.3), "z")
    s = K.fuse(s, K.cyl(2.3, 18.0, (MX - 18.0, 0, P["wing_z"]), "x"))
    s = K.cut(s, K.cyl(0.75, top - P["wing_z"] + 10, (MX, 0, P["wing_z"]), "z"))
    s = K.cut(s, K.cyl(0.75, 20.0, (MX - 19.0, 0, P["wing_z"]), "x"))
    s = K.fuse(s, K.cyl(2.0, 10.0, (MX, 0, top), "z"))
    s = K.cut(s, K.cyl(0.75, 12.0, (MX, 0, top - 1), "z"))
    # collar that sits on the top wall
    s = K.fuse(s, K.box(14.0, 14.0, 2.0, (MX - 7.0, -7.0, P["ts_half"] + P["wall"])))
    return s


def part_probe_plug():
    s = K.cyl(P["probe_hole_d"] / 2 - 0.15, P["wall"] + 0.5, (MX, 0, P["ts_half"] - 0.5), "z")
    s = K.fuse(s, K.cyl(5.0, 2.0, (MX, 0, P["ts_half"] + P["wall"]), "z"))
    return s


def part_zero_gauge():
    """Right-angle block: sits on the floor and touches the strut face for zero."""
    s = K.box(30.0, 10.0, 30.0, (MX + P["strut_t"] / 2 + 0.3, 20.0, FLOOR_TOP))
    s = K.cut(s, K.box(26.0, 12.0, 26.0, (MX + P["strut_t"] / 2 + 4.3, 19.0, FLOOR_TOP + 2.0)))
    return s


def part_ebox():
    ix, iy, iz = P["ebox_inner"]
    w = P["ebox_wall"]
    x0, y0, z0 = -120.0, 80.0, P["table_z"]
    s = K.box(ix + 2 * w, iy + 2 * w, iz + w, (x0, y0, z0))
    s = K.cut(s, K.box(ix, iy, iz + 1, (x0 + w, y0 + w, z0 + w)))
    # card slots for an ESP32 DevKit (28.5 wide) and two HX711 boards (21 wide)
    for (cx, cw) in ((x0 + w + 10, 28.5), (x0 + w + 50, 21.0), (x0 + w + 80, 21.0)):
        for sgn in (0, 1):
            rail = K.box(2.0, 6.0, iz - 4, (cx + sgn * (cw + 2.0), y0 + w, z0 + w))
            s = K.fuse(s, rail)
            rail2 = K.box(2.0, 6.0, iz - 4, (cx + sgn * (cw + 2.0), y0 + w + iy - 6.0, z0 + w))
            s = K.fuse(s, rail2)
    # USB and cable cut-outs
    s = K.cut(s, K.box(14.0, w + 2, 9.0, (x0 + w + 10 + 7.0, y0 - 1, z0 + w + 4)))
    s = K.cut(s, K.box(w + 2, 12.0, 8.0, (x0 + w + ix - 1, y0 + w + iy / 2 - 6, z0 + w + 2)))
    # magnet pockets in the rim for the lid
    md, mt = P["magnet_d"] + 0.3, P["magnet_t"] + 0.2
    for (mx, my) in ((x0 + w / 2 + 2, y0 + w / 2 + 2), (x0 + ix + 1.5 * w - 2, y0 + w / 2 + 2),
                     (x0 + w / 2 + 2, y0 + iy + 1.5 * w - 2), (x0 + ix + 1.5 * w - 2, y0 + iy + 1.5 * w - 2)):
        pass
    return s


def part_ebox_lid():
    ix, iy, iz = P["ebox_inner"]
    w = P["ebox_wall"]
    x0, y0, z0 = -120.0, 80.0, P["table_z"]
    top = z0 + iz + w
    s = K.box(ix + 2 * w, iy + 2 * w, 2.0, (x0, y0, top))
    inner = K.box(ix - 0.4, iy - 0.4, 3.0, (x0 + w + 0.2, y0 + w + 0.2, top - 3.0))
    s = K.fuse(s, inner)
    s = K.cut(s, K.box(ix - 0.4 - 2 * 2.0, iy - 0.4 - 2 * 2.0, 3.5, (x0 + w + 2.2, y0 + w + 2.2, top - 3.5)))
    return s


def part_cam_clip():
    """Holder for an ESP32-CAM board that sticks to a window clip frame with magnets."""
    yo = P["ts_half"] + P["wall"] + P["window_boss"] + 3.0
    s = K.box(44.0, 6.0, 32.0, (P["window_x0"] + 20, yo, -16.0))
    s = K.cut(s, K.box(41.0, 2.0, 28.0, (P["window_x0"] + 21.5, yo + 3.0, -14.0)))   # PCB slot
    s = K.cut(s, K.box(30.0, 8.0, 20.0, (P["window_x0"] + 27, yo - 1, -10.0)))       # lens window
    md, mt = P["magnet_d"] + 0.3, P["magnet_t"] + 0.2
    for dx in (4.0, 40.0):
        s = K.cut(s, K.cyl(md / 2, mt, (P["window_x0"] + 20 + dx, yo, 0.0), "y"))
    return s


# ---- reference (non-printed) parts for interference checks ------------------
def ref_fan():
    f = P["fan_frame"] / 2
    s = K.box(P["fan_depth"], 2 * f, 2 * f, (X_DIFF1, -f, -f))
    return s


def ref_servo():
    s = K.box(P["servo_L"], P["servo_H"], P["servo_W"], (SERVO_X0, SERVO_Y0, SERVO_Z[0]))
    # tabs
    fy = SERVO_Y0 + P["servo_flange_from_top"]
    s = K.fuse(s, K.box(P["servo_L"] + 2 * P["servo_tab"], P["servo_flange_t"], P["servo_W"],
                        (SERVO_X0 - P["servo_tab"], fy, SERVO_Z[0])))
    # output shaft stub
    s = K.fuse(s, K.cyl(2.5, P["servo_horn_gap"] + 0.01, (MX, SERVO_Y0 - P["servo_horn_gap"], DRUM_Z), "y"))
    return s


def ref_lift_cell():
    return K.box(CELL_W, CELL_L, CELL_T, (LIFT_X - CELL_W / 2, LIFT_Y[0], LIFT_TOP - CELL_T))


def ref_drag_cell():
    return K.box(CELL_T, CELL_W, CELL_L, (DRAG_X - CELL_T / 2, DRAG_CELL_Y - CELL_W / 2, DRAG_Z0))


def ref_window_sheet(sgn):
    wx0, wx1, wz = P["window_x0"], P["window_x1"], P["window_half_z"]
    m, rec = P["window_margin"], P["window_recess"]
    yo = P["ts_half"] + P["wall"] + P["window_boss"]
    y0 = yo - rec if sgn > 0 else -yo
    return K.box(wx1 - wx0 + 2 * m - 0.4, 1.0, 2 * (wz + m) - 0.4, (wx0 - m + 0.2, y0 + 0.1, -wz - m + 0.2))


def ref_car():
    L, W, H = P["car_len"] - 4, P["car_w"] - 6, 24.0
    return K.box(L, W, H, (MX - L / 2, -W / 2, P["car_tray_z"] + P["tray_t"]))


def ref_as5600():
    return K.box(22.0, 1.6, 22.0, (MX - 11.0, AS5600_Y[0], DRUM_Z - 11.0))


# ================================================================ build all
def build_all(verbose=True):
    def log(msg):
        if verbose:
            print(msg, flush=True)

    log("bellmouth"); add("bellmouth_quarter", part_bellmouth_quarter(), [("y", 90)],
                         "Print 4. Flat face down.", qty=4)
    log("settling chamber"); add("settling_chamber", part_settling_chamber(), [("y", 90)],
                                "Open end up. No supports.")
    hc, nholes, x_hc0 = part_honeycomb()
    log("honeycomb (%d cells)" % nholes)
    add("honeycomb", hc, [("y", 90)], "%d hexagonal cells. Print with 0.4 mm nozzle, 2 walls, no infill." % nholes)
    # stack spacers and screens (from downstream): lip | screen B | spacer 12 | screen A | spacer 12 | honeycomb | spacer 28
    xB = X_C_IN - P["lip_t"] - P["screen_t"]
    xS1 = xB - 12.0
    xA = xS1 - P["screen_t"]
    xS2 = xA - 12.0
    xS3 = x_hc0 - 28.0
    log("stack"); add("screen_frame", part_screen_frame(xB), [("y", 90)], "Print 2. Glue mesh on the downstream face.", qty=2)
    add("screen_frame_A_pos", part_screen_frame(xA), [("y", 90)], "Same part as screen_frame (position reference only).", reference=True)
    add("spacer_12", part_spacer(12.0, xS1), [("y", 90)], "Print 2.", qty=2)
    add("spacer_12_pos2", part_spacer(12.0, xS2), [("y", 90)], "Same part as spacer_12 (position reference only).", reference=True)
    add("spacer_28", part_spacer(28.0, xS3), [("y", 90)], "Print 1.")
    log("contraction 1"); add("contraction_1", part_contraction(X_C_IN, X_C_MID), [("y", 90)], "Large end down.")
    log("contraction 2"); add("contraction_2", part_contraction(X_C_MID, X_TS0), [("y", 90)], "Large end down.")
    log("test section 1"); add("test_section_1", part_ts1(), [("y", 90)], "Stand on a flange. Drill the 1.2 mm taps clean.")
    log("test section 2"); add("test_section_2", part_ts2(), [("y", 90)], "Stand on a flange. Window openings need no support when printed vertically.")
    add("window_clip", part_window_clip(), [("x", -90)], "Print 2. Flat side down.", qty=2)
    log("diffuser"); add("diffuser", part_diffuser(), [("y", 90)], "Fan plate up. 4 hex nut traps face the duct.")
    log("fan guard"); add("fan_guard", part_fan_guard(), [("y", -90)], "Flat side down.")
    log("balance bay"); add("balance_bay", part_bay(), [], "Open side up. Stop fingers need supports.")
    log("platform"); add("platform", part_platform(), [], "Plate down, hanger up. Supports under the hanger and posts.")
    add("bracket", part_bracket(), [], "Arm down. Supports under the block overhang.")
    add("drum", part_drum(), [("x", 90)], "Flat (horn) face down. Supports in the socket are not needed.")
    sl, _ = part_strut(long=True); add("strut_long", sl, [], "Vertical. Brim recommended.")
    ss, _ = part_strut(long=False); add("strut_short", ss, [], "Vertical. Brim recommended.")
    log("wings"); add("wing_naca0012", part_wing("0012", "wing_naca0012"), [("x", 180)], "Upside down, pylon up. Supports in the socket only.")
    add("wing_naca4412", part_wing("4412", "wing_naca4412"), [("x", 180)], "Upside down, pylon up. Supports in the socket only.")
    add("wing_flat_plate", part_wing("plate", "wing_flat_plate"), [("x", 180)], "Upside down, pylon up.")
    log("car tray"); add("car_tray", part_car_tray(), [], "Flat. Supports under the neck.")
    add("ground_board", part_ground_board(), [("x", 180)], "Upside down (pegs up).")
    log("stands"); add("stand_settling", part_stand(X_SC_IN + 30.0, 2 * (P["sc_half"] + P["wall"]), -(P["sc_half"] + P["wall"]), "stand_settling"), [], "Flat.")
    add("stand_test_section", part_stand(30.0, 2 * (P["ts_half"] + P["wall"]), FLOOR_BOT, "stand_test_section"), [], "Flat.")
    add("stand_fan", part_fan_stand(), [], "Flat.")
    add("tap_barb", part_tap_barb(), [], "Print 6. Flange down.", qty=6)
    add("pitot_wand", part_pitot_wand(), [("x", 90)], "On its side so the 1.5 mm channels print clean.")
    add("probe_plug", part_probe_plug(), [("x", 180)], "Cap down.")
    add("zero_gauge", part_zero_gauge(), [], "Flat.")
    add("electronics_box", part_ebox(), [], "Open side up.")
    add("electronics_lid", part_ebox_lid(), [("x", 180)], "Flat side down.")
    add("cam_clip", part_cam_clip(), [("x", -90)], "Optional. Flat side down.")
    # reference parts
    add("ref_fan", ref_fan(), [], "ARCTIC S12038-8K envelope", reference=True)
    add("ref_servo", ref_servo(), [], "MG90S envelope", reference=True)
    add("ref_lift_cell", ref_lift_cell(), [], "200 g bar cell envelope", reference=True)
    add("ref_drag_cell", ref_drag_cell(), [], "100 g bar cell envelope", reference=True)
    add("ref_window_sheet_R", ref_window_sheet(1), [], "1 mm clear sheet", reference=True)
    add("ref_window_sheet_L", ref_window_sheet(-1), [], "1 mm clear sheet", reference=True)
    add("ref_car", ref_car(), [], "1:64 car envelope", reference=True)
    add("ref_as5600", ref_as5600(), [], "AS5600 board envelope", reference=True)
    return PARTS


def print_placement(solid, rot):
    s = solid
    for axis, deg in rot:
        s = K.rotate(s, (0, 0, 0), axis, deg)
    bb = K.bbox(s)
    s = K.translate(s, (-(bb[0] + bb[3]) / 2, -(bb[1] + bb[4]) / 2, -bb[2]))
    return s


def export_all(outdir):
    stl_dir = os.path.join(outdir, "stl")
    asm_dir = os.path.join(outdir, "assembly_stl")
    step_dir = os.path.join(outdir, "step")
    for d in (stl_dir, asm_dir, step_dir):
        os.makedirs(d, exist_ok=True)
    manifest = {"params": {k: (list(v) if isinstance(v, tuple) else v) for k, v in P.items()},
                "kernel": K.name, "parts": {}}
    for name, info in PARTS.items():
        s = info["solid"]
        bb = K.bbox(s)
        rec = {"reference": info["reference"], "note": info["note"], "qty": info["qty"],
               "configs": info["configs"],
               "assembly_bbox": [round(v, 3) for v in bb], "volume_mm3": round(K.volume(s), 1),
               "valid": bool(K.is_valid(s))}
        K.export_stl(s, os.path.join(asm_dir, name + ".stl"))
        if not info["reference"]:
            ps = print_placement(s, info["print_rot"])
            pbb = K.bbox(ps)
            rec["print_bbox"] = [round(v, 3) for v in pbb]
            rec["print_size"] = [round(pbb[3] - pbb[0], 2), round(pbb[4] - pbb[1], 2), round(pbb[5] - pbb[2], 2)]
            K.export_stl(ps, os.path.join(stl_dir, name + ".stl"))
            K.export_step(ps, os.path.join(step_dir, name + ".step"))
        manifest["parts"][name] = rec
        print("  exported %-24s vol=%9.0f mm3  print=%s" % (name, rec["volume_mm3"], rec.get("print_size", "-")), flush=True)
    with open(os.path.join(outdir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest


if __name__ == "__main__":
    outdir = HERE
    print("Benairy CAD generator, kernel:", K.name)
    build_all()
    export_all(outdir)
    if IN_FREECAD and make_document is not None:
        path = make_document("Benairy", PARTS, P, outdir)
        print("FreeCAD document written:", path)
    print("done")
