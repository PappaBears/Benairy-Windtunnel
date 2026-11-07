"""FreeCAD backend for the Benairy CAD generator.

Run inside FreeCAD (GUI macro or `freecadcmd benairy_cad.py`). It has the
same interface as kernel_cq.py. The document also gets a spreadsheet
with the parameters, so you can read them in the FreeCAD GUI.
"""
from __future__ import annotations

import FreeCAD  # noqa: F401  (available only inside FreeCAD)
import Part
from FreeCAD import Base

AXES = {"x": Base.Vector(1, 0, 0), "y": Base.Vector(0, 1, 0), "z": Base.Vector(0, 0, 1)}


def _plane_points(pts2d, plane, offset):
    out = []
    for u, v in pts2d:
        if plane == "xy":
            out.append(Base.Vector(u, v, offset))
        elif plane == "xz":
            out.append(Base.Vector(u, offset, v))
        elif plane == "yz":
            out.append(Base.Vector(offset, u, v))
        else:
            raise ValueError(plane)
    return out


def _closed(pts):
    pts = list(pts)
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    return pts


class Kernel:
    name = "freecad"

    def box(self, dx, dy, dz, at=(0, 0, 0)):
        return Part.makeBox(dx, dy, dz, Base.Vector(*at))

    def cyl(self, r, h, at=(0, 0, 0), axis="z"):
        return Part.makeCylinder(r, h, Base.Vector(*at), AXES[axis])

    def prism(self, pts2d, h, plane="xy", offset=0.0, holes=None):
        normal = {"xy": Base.Vector(0, 0, 1), "xz": Base.Vector(0, 1, 0),
                  "yz": Base.Vector(1, 0, 0)}[plane]
        outer = Part.makePolygon(_closed(_plane_points(pts2d, plane, offset)))
        wires = [outer] + [Part.makePolygon(_closed(_plane_points(hp, plane, offset)))
                           for hp in (holes or [])]
        face = Part.Face(wires)
        return face.extrude(normal * h)

    def loft(self, sections, ruled=False):
        wires = [Part.makePolygon(_closed([Base.Vector(*p) for p in sec])) for sec in sections]
        return Part.makeLoft(wires, True, ruled)

    def fuse(self, a, b):
        return a.fuse(b).removeSplitter()

    def cut(self, a, b):
        return a.cut(b).removeSplitter()

    def common(self, a, b):
        return a.common(b)

    def translate(self, s, d):
        c = s.copy()
        c.translate(Base.Vector(*d))
        return c

    def rotate(self, s, point, axis, deg):
        c = s.copy()
        c.rotate(Base.Vector(*point), AXES[axis], deg)
        return c

    def bbox(self, s):
        bb = s.BoundBox
        return (bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax)

    def volume(self, s):
        return s.Volume

    def is_valid(self, s):
        return s.isValid()

    def export_stl(self, s, path, tol=0.05, ang_tol=0.2):
        import Mesh
        import MeshPart
        m = MeshPart.meshFromShape(Shape=s, LinearDeflection=tol, AngularDeflection=ang_tol,
                                   Relative=False)
        m.write(path)

    def export_step(self, s, path):
        s.exportStep(path)


def make_document(name, parts, params, outdir):
    """Create a FreeCAD document with one Part::Feature per part and a
    parameter spreadsheet, then save it as <outdir>/<name>.FCStd."""
    import os
    doc = FreeCAD.newDocument(name)
    sheet = doc.addObject("Spreadsheet::Sheet", "Params")
    sheet.set("A1", "Parameter")
    sheet.set("B1", "Value (mm unless noted)")
    row = 2
    for k, v in params.items():
        sheet.set("A%d" % row, str(k))
        sheet.set("B%d" % row, str(v))
        row += 1
    grp_print = doc.addObject("App::DocumentObjectGroup", "PrintedParts")
    grp_ref = doc.addObject("App::DocumentObjectGroup", "ReferenceParts")
    for pname, info in parts.items():
        obj = doc.addObject("Part::Feature", pname)
        obj.Shape = info["solid"]
        obj.Label = pname
        (grp_ref if info.get("reference") else grp_print).addObject(obj)
    doc.recompute()
    path = os.path.join(outdir, name + ".FCStd")
    doc.saveAs(path)
    return path
