from dataclasses import dataclass
import numpy as np
import trimesh


def make_pyramid(base_size, height):
    """One four-sided scale.

    There is deliberately no standalone pyramid *lattice* builder. Scales cannot
    interlink with each other, so a sheet of nothing but scales is a tray of
    loose parts. Scales are mounted on a ring lattice instead - see
    hybrid_mesh.HybridMeshBuilder, which backs both the `pyramid` (scale on
    every ring) and `hybrid` (scale on alternating rings) link types.
    """
    h = base_size / 2
    verts = np.array([[-h, -h, 0], [h, -h, 0], [h, h, 0], [-h, h, 0], [0, 0, height]])
    faces = np.array([[0, 1, 2], [0, 2, 3], [0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4]])
    return trimesh.Trimesh(vertices=verts, faces=faces, process=True)
