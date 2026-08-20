from dataclasses import dataclass
import numpy as np
import trimesh
from .torus import make_torus

# European 4-in-1. These three constants are the lattice, expressed as multiples
# of the ring centreline radius, and they are not free parameters: they were
# found by searching for a configuration where every ring is topologically
# linked to exactly four neighbours while no two ring solids come closer than
# the clearance gap. tests/test_interlink.py re-derives both properties from the
# generated geometry, so changing any of these without re-running that test will
# produce fabric that either falls apart or fuses solid.
TILT_DEGREES = 30.0
COLUMN_PITCH_RATIO = 2.50
ROW_PITCH_RATIO = 0.65

# Ratio of the ring's hole to its wire thickness. Four wires pass through every
# hole in 4-in-1, so a fat wire in a small ring cannot link at all.
MIN_ASPECT_RATIO = 4.0


def drape_z(row, total_rows, curvature):
    """Height of a row on the drape curve: zero at both edges, peak in the middle."""
    if total_rows <= 1:
        return 0.0
    t = row / (total_rows - 1)
    return curvature * 20.0 * (1 - (2 * t - 1) ** 2)


def ring_tilt(row, tilt_degrees=TILT_DEGREES):
    """Rings lean one way on even rows and the other way on odd rows.

    Two parallel rings can never link - a ring in a parallel plane never crosses
    this ring's disk - so the alternating lean is what makes the fabric a fabric.
    """
    return np.radians(tilt_degrees) * (-1.0 if row % 2 else 1.0)


def ring_normal(row, tilt_degrees=TILT_DEGREES):
    angle = ring_tilt(row, tilt_degrees)
    return np.array([0.0, -np.sin(angle), np.cos(angle)])


@dataclass
class RingMeshConfig:
    outer_diameter: float = 8.0
    tube_radius: float = 0.5
    clearance_gap: float = 0.5
    rows: int = 20
    columns: int = 30
    drape_curvature: float = 0.3
    tilt_degrees: float = TILT_DEGREES


class RingMeshBuilder:
    def __init__(self, config: RingMeshConfig):
        self.config = config
        self._anchor_points = []

    @property
    def centerline_radius(self):
        return self.config.outer_diameter / 2 - self.config.tube_radius

    @property
    def aspect_ratio(self):
        return (self.centerline_radius - self.config.tube_radius) / self.config.tube_radius

    def validate_linkable(self):
        c = self.config
        if self.centerline_radius <= c.tube_radius:
            raise ValueError(
                f"ring_outer_diameter {c.outer_diameter} is too small for "
                f"ring_tube_radius {c.tube_radius}: the ring has no hole")
        if self.aspect_ratio < MIN_ASPECT_RATIO:
            wanted = c.tube_radius * 2 * (MIN_ASPECT_RATIO + 2)
            raise ValueError(
                f"ring hole is too small to interlink: aspect ratio "
                f"{self.aspect_ratio:.2f} < {MIN_ASPECT_RATIO}. With "
                f"ring_tube_radius {c.tube_radius} you need ring_outer_diameter "
                f">= {wanted:.2f}, or keep the diameter and drop the tube radius "
                f"to {c.outer_diameter / (2 * (MIN_ASPECT_RATIO + 2)):.2f}")

    def column_pitch(self):
        return COLUMN_PITCH_RATIO * self.centerline_radius

    def row_pitch(self):
        return ROW_PITCH_RATIO * self.centerline_radius

    def ring_center(self, row, col):
        dx, dy = self.column_pitch(), self.row_pitch()
        x = col * dx + (dx / 2 if row % 2 else 0.0)
        z = drape_z(row, self.config.rows, self.config.drape_curvature)
        return np.array([x, row * dy, z])

    def make_ring(self, row):
        c = self.config
        ring = make_torus(c.outer_diameter, c.tube_radius)
        ring.apply_transform(
            trimesh.transformations.rotation_matrix(ring_tilt(row, c.tilt_degrees), [1, 0, 0]))
        return ring

    def link_sites(self):
        """Where a connector ring must sit to link the first row of fabric.

        Row -1 of the same lattice. A ring placed here links rings (0, col-1)
        and (0, col) exactly the way a real neighbouring row would, so the
        connector is held by the same verified geometry as the fabric itself.
        """
        c = self.config
        return [(self.ring_center(-1, col), ring_normal(-1, c.tilt_degrees))
                for col in range(c.columns)]

    def anchor_points(self):
        return self._anchor_points

    def generate(self):
        self.validate_linkable()
        c = self.config
        parts = []
        self._anchor_points = []
        for row in range(c.rows):
            for col in range(c.columns):
                ring = self.make_ring(row)
                center = self.ring_center(row, col)
                ring.apply_translation(center)
                parts.append(ring)
                if row == 0:
                    self._anchor_points.append(center)
        return trimesh.util.concatenate(parts)


def build_handle_mesh(length_mm, width_rows=3, ring_outer_diameter=14.0, ring_tube_radius=0.875,
                      clearance_gap=0.6):
    cfg = RingMeshConfig(outer_diameter=ring_outer_diameter, tube_radius=ring_tube_radius,
                         clearance_gap=clearance_gap, rows=2, columns=width_rows,
                         drape_curvature=0.0)
    builder = RingMeshBuilder(cfg)
    rows = max(2, int(round(length_mm / builder.row_pitch())))
    builder.config.rows = rows
    return builder.generate(), builder
