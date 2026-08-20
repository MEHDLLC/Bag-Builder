from dataclasses import dataclass
from typing import List, Tuple
import numpy as np
import trimesh
from .torus import make_torus


@dataclass
class RingMeshConfig:
    outer_diameter: float = 8.0
    tube_radius: float = 1.0
    clearance_gap: float = 0.5
    rows: int = 20
    columns: int = 30
    drape_curvature: float = 0.3


class RingMeshBuilder:
    def __init__(self, config: RingMeshConfig):
        self.config = config
        self._anchor_points = []

    def _row_col_spacing(self):
        c = self.config
        return c.outer_diameter - c.tube_radius

    def anchor_points(self):
        return self._anchor_points

    def generate(self):
        c = self.config
        spacing = self._row_col_spacing()
        parts = []
        self._anchor_points = []
        for row in range(c.rows):
            y = row * spacing * 0.87
            row_offset = (spacing / 2) if row % 2 else 0.0
            z_curve = self._drape_z(row, c.rows)
            for col in range(c.columns):
                x = col * spacing + row_offset
                ring = make_torus(c.outer_diameter, c.tube_radius)
                if row % 2 == 0:
                    ring.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
                translation = [x, y, z_curve]
                ring.apply_translation(translation)
                parts.append(ring)
                if row == 0:
                    self._anchor_points.append(np.array(translation))
        return trimesh.util.concatenate(parts)

    def _drape_z(self, row, total_rows):
        c = self.config
        if total_rows <= 1:
            return 0.0
        t = row / (total_rows - 1)
        return c.drape_curvature * 20.0 * (1 - (2 * t - 1) ** 2)


def build_handle_mesh(length_mm, width_rows=3, ring_outer_diameter=14.0, ring_tube_radius=2.2, clearance_gap=0.6):
    spacing = ring_outer_diameter - ring_tube_radius
    rows = max(2, int(length_mm / (spacing * 0.87)))
    cfg = RingMeshConfig(outer_diameter=ring_outer_diameter, tube_radius=ring_tube_radius,
                          clearance_gap=clearance_gap, rows=rows, columns=width_rows, drape_curvature=0.0)
    builder = RingMeshBuilder(cfg)
    mesh = builder.generate()
    return mesh, builder
