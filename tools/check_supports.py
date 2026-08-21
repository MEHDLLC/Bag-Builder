"""Does a part print without supports?

Slices a mesh and asks, layer by layer, whether anything appears with nothing
underneath it. Two failures matter and they are not the same:

* an **island** - a region touching nothing in the layer below. The nozzle has
  to extrude into air. Only supports fix this.
* a **cantilever** - attached to the layer below along one edge but overhanging.
  Short ones print; long ones droop.

    python tools/check_supports.py part.stl --layer 0.2
"""
import argparse
import sys

import numpy as np
import shapely.ops
import trimesh


def layers(mesh, layer_height):
    lo, hi = mesh.bounds[0][2], mesh.bounds[1][2]
    for z in np.arange(lo + layer_height / 2, hi, layer_height):
        section = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
        if section is None:
            continue
        planar, _ = section.to_planar()
        polygons = list(planar.polygons_full)
        if polygons:
            yield z - lo, shapely.ops.unary_union(polygons)


def report(mesh, layer_height, quiet=False):
    previous = None
    islands = 0
    worst = 0.0
    for z, current in layers(mesh, layer_height):
        if previous is not None:
            new = current.difference(previous)
            pieces = new.geoms if hasattr(new, "geoms") else [new]
            floating = [g for g in pieces if g.area > 1e-6 and not g.intersects(previous)]
            islands += len(floating)
            worst = max(worst, new.area)
            if not quiet and new.area > 0.01:
                tag = f"  {len(floating)} ISLAND(S)" if floating else "  attached"
                print(f"  z={z:5.2f}  unsupported {new.area:6.2f} mm2{tag}")
        previous = current
    return islands, worst


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path")
    ap.add_argument("--layer", type=float, default=0.2)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    mesh = trimesh.load(args.path, force="mesh")
    islands, worst = report(mesh, args.layer, args.quiet)
    print(f"\nislands: {islands}   worst unsupported layer: {worst:.2f} mm2")
    print("-> needs supports" if islands else "-> no islands; supports not required")
    return 1 if islands else 0


if __name__ == "__main__":
    sys.exit(main())
