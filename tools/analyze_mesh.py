"""Characterise a mesh STL the way this project's fabric is characterised.

Point it at any chainmail-ish STL - one of ours, or a reference model from
somewhere else - and it reports the things that decide whether the geometry is
reproducible here: how many separate bodies it has, whether those bodies are
rings, how big the rings are, how far apart they sit, whether they are actually
linked, and how much clearance the design left for the printer.

    python tools/analyze_mesh.py fabric.stl

Output is a few KB of text, so it can be pasted into a conversation when the
file itself is too big to move around.
"""
import argparse
import sys

import networkx as nx
import numpy as np
import trimesh

sys.path.insert(0, ".")
from src.mesh.interlink import is_linked  # noqa: E402


def split_bodies(mesh):
    """Connected components of the face-adjacency graph.

    trimesh's own split() wants scipy; networkx is already a dependency here.
    """
    graph = nx.Graph()
    graph.add_nodes_from(range(len(mesh.faces)))
    graph.add_edges_from(mesh.face_adjacency)
    return list(nx.connected_components(graph))


def body_mesh(mesh, face_ids):
    return mesh.submesh([sorted(face_ids)], append=True)


def ring_fit(body):
    """Fit a torus to a body: plane normal, centreline radius, tube radius.

    The ring's plane is the one its vertices vary in least, so the smallest
    principal component of the vertex cloud is the normal.
    """
    verts = body.vertices
    center = verts.mean(axis=0)
    centred = verts - center
    _, _, vh = np.linalg.svd(centred, full_matrices=False)
    normal = vh[2]
    in_plane = np.linalg.norm(centred - np.outer(centred @ normal, normal), axis=1)
    centerline = (in_plane.max() + in_plane.min()) / 2
    tube = (in_plane.max() - in_plane.min()) / 2
    return center, normal, centerline, tube


def genus(body):
    """0 for a blob, 1 for a ring. Only meaningful on a closed surface."""
    if not body.is_watertight:
        return None
    euler = len(body.vertices) - len(body.edges_unique) + len(body.faces)
    return (2 - euler) // 2


def min_gap(a, b, cap=400):
    """Closest approach between two bodies, from subsampled vertices."""
    pa = a.vertices[:: max(1, len(a.vertices) // cap)]
    pb = b.vertices[:: max(1, len(b.vertices) // cap)]
    return float(np.linalg.norm(pa[:, None, :] - pb[None, :, :], axis=2).min())


def describe(path, max_bodies, sample):
    mesh = trimesh.load(path, force="mesh")
    print(f"file            {path}")
    print(f"triangles       {len(mesh.faces):,}")
    lo, hi = mesh.bounds
    size = hi - lo
    print(f"bounding box    {size[0]:.2f} x {size[1]:.2f} x {size[2]:.2f} mm")

    print("\nsplitting into bodies (this is the slow part)...", flush=True)
    components = split_bodies(mesh)
    print(f"separate bodies {len(components):,}")
    if len(components) == 1:
        print("  -> one connected solid: a flexure lattice or a fused sheet,")
        print("     NOT interlinked rings. Its flexibility comes from thin")
        print("     hinges in the solid rather than from links.")

    order = sorted(components, key=len, reverse=True)
    sizes = np.array([len(c) for c in order])
    print(f"faces per body  min {sizes.min()}  median {int(np.median(sizes))}  max {sizes.max()}")
    print(f"distinct sizes  {len(set(sizes.tolist()))}  "
          f"(1 means every body is the same part repeated)")

    examine = order[:max_bodies]
    bodies = [body_mesh(mesh, c) for c in examine]

    rings, solids, open_shells = [], [], []
    for b in bodies:
        g = genus(b)
        (rings if g == 1 else solids if g == 0 else open_shells).append(b)
    print(f"\nof the {len(bodies)} largest bodies examined:")
    print(f"  ring-shaped (genus 1)   {len(rings)}")
    print(f"  solid blobs  (genus 0)  {len(solids)}")
    print(f"  not watertight          {len(open_shells)}")

    if not rings:
        print("\nNo ring-shaped bodies found - nothing to measure as chainmail.")
        return

    fits = [ring_fit(b) for b in rings]
    centerlines = np.array([f[2] for f in fits])
    tubes = np.array([f[3] for f in fits])
    outer = 2 * (centerlines + tubes)
    print("\nring geometry (mm), across the rings examined:")
    print(f"  outer diameter    {outer.mean():.3f}  (spread {outer.std():.3f})")
    print(f"  centreline radius {centerlines.mean():.3f}")
    print(f"  wire radius       {tubes.mean():.3f}   wire diameter {2*tubes.mean():.3f}")
    aspect = (centerlines.mean() - tubes.mean()) / tubes.mean()
    print(f"  aspect ratio      {aspect:.2f}   (this project needs >= 4.0)")

    centers = np.array([f[0] for f in fits])
    normals = np.array([f[1] for f in fits])
    leans = np.degrees(np.arccos(np.clip(np.abs(normals @ np.array([0, 0, 1.0])), 0, 1)))
    print(f"  lean off the sheet plane  {leans.mean():.1f} deg "
          f"(spread {leans.std():.1f}); distinct leans suggest alternating rows")

    # Nearest-neighbour spacing between ring centres.
    d = np.linalg.norm(centers[:, None, :] - centers[None, :, :], axis=2)
    np.fill_diagonal(d, np.inf)
    nearest = d.min(axis=1)
    print(f"\nlattice: nearest ring centre {nearest.mean():.3f} mm "
          f"(min {nearest.min():.3f}, max {nearest.max():.3f})")

    probe = min(len(rings), sample)
    print(f"\nlinkage and clearance, sampling the {probe} closest ring pairs:")
    linked_counts, gaps = [], []
    for i in range(probe):
        neighbours = np.argsort(d[i])[:6]
        count = 0
        for j in neighbours:
            if not np.isfinite(d[i][j]):
                continue
            if is_linked(centers[i], normals[i], centers[j], normals[j],
                         float(centerlines[[i, j]].mean())):
                count += 1
            else:
                gaps.append(min_gap(rings[i], rings[j]))
        linked_counts.append(count)
    linked_counts = np.array(linked_counts)
    modal = np.bincount(linked_counts).argmax()
    print(f"  links per ring   most common {modal}  "
          f"(mean {linked_counts.mean():.2f}, min {linked_counts.min()}, "
          f"max {linked_counts.max()})")
    print("  edge rings have fewer links than interior ones, so read the most")
    print("  common value rather than the mean on a small sample.")
    if linked_counts.max() == 0:
        print("  -> NOTHING is linked. Rings are merely adjacent, so this is not")
        print("     a chainmail at all - it would fall apart or print as a slab.")
    elif modal == 4:
        print("  -> consistent with European 4-in-1, which this project builds.")
    elif modal == 6:
        print("  -> six links per ring: a denser weave than this project builds.")
    else:
        print(f"  -> {modal} links per ring: some weave this project does not build yet.")
    if gaps:
        print(f"  clearance between unlinked neighbours: min {min(gaps):.3f} mm "
              f"(this is the printer tolerance the design relied on)")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path")
    ap.add_argument("--max-bodies", type=int, default=400,
                    help="how many bodies to measure in detail (default 400)")
    ap.add_argument("--sample", type=int, default=40,
                    help="how many rings to test for linkage (default 40)")
    args = ap.parse_args()
    describe(args.path, args.max_bodies, args.sample)


if __name__ == "__main__":
    main()
