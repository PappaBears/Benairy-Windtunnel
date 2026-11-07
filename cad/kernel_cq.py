"""CadQuery/OCCT backend for the Benairy CAD generator.

The FreeCAD backend (kernel_freecad.py) has the same interface, so the
part definitions in benairy_cad.py run in both environments.
"""
from __future__ import annotations

import math

import cadquery as cq
from cadquery import Vector

AXES = {"x": Vector(1, 0, 0), "y": Vector(0, 1, 0), "z": Vector(0, 0, 1)}


def _plane_points(pts2d, plane, offset):
    """Map 2-D points to 3-D on an axis plane. plane 'xy' at z=offset etc."""
    out = []
    for u, v in pts2d:
        if plane == "xy":
            out.append(Vector(u, v, offset))
        elif plane == "xz":
            out.append(Vector(u, offset, v))
        elif plane == "yz":
            out.append(Vector(offset, u, v))
        else:
            raise ValueError(plane)
    return out


class Kernel:
    name = "cadquery"

    # ---- primitives
    def box(self, dx, dy, dz, at=(0, 0, 0)):
        return cq.Solid.makeBox(dx, dy, dz, Vector(*at))

    def cyl(self, r, h, at=(0, 0, 0), axis="z"):
        return cq.Solid.makeCylinder(r, h, Vector(*at), AXES[axis])

    def prism(self, pts2d, h, plane="xy", offset=0.0, holes=None):
        normal = {"xy": Vector(0, 0, 1), "xz": Vector(0, 1, 0), "yz": Vector(1, 0, 0)}[plane]
        outer = cq.Wire.makePolygon(_plane_points(pts2d, plane, offset), close=True)
        inner = [cq.Wire.makePolygon(_plane_points(hp, plane, offset), close=True)
                 for hp in (holes or [])]
        face = cq.Face.makeFromWires(outer, inner)
        return cq.Solid.extrudeLinear(face, normal * h)

    def loft(self, sections, ruled=False):
        wires = [cq.Wire.makePolygon([Vector(*p) for p in sec], close=True) for sec in sections]
        return cq.Solid.makeLoft(wires, ruled)

    # ---- booleans
    def fuse(self, a, b):
        return a.fuse(b).clean()

    def cut(self, a, b):
        return a.cut(b).clean()

    def common(self, a, b):
        return a.intersect(b)

    # ---- transforms (return new shapes)
    def translate(self, s, d):
        return s.translate(Vector(*d))

    def rotate(self, s, point, axis, deg):
        p = Vector(*point)
        return s.rotate(p, p + AXES[axis], deg)

    # ---- queries
    def bbox(self, s):
        bb = s.BoundingBox()
        return (bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax)

    def volume(self, s):
        return s.Volume()

    def is_valid(self, s):
        return s.isValid()

    # ---- export
    def export_stl(self, s, path, tol=0.05, ang_tol=0.2):
        cq.exporters.export(cq.Workplane("XY").add(s), path, tolerance=tol,
                            angularTolerance=ang_tol)

    def export_step(self, s, path):
        cq.exporters.export(cq.Workplane("XY").add(s), path)
