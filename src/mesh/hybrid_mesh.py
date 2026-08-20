from dataclasses import dataclass
import numpy as np
import trimesh
from .pyramid_mesh import make_pyramid
from .ring_mesh import RingMeshBuilder, RingMeshConfig, ring_normal


@dataclass
class HybridMeshConfig:
    outer_diameter: float = 8.0
    tube_radius: float = 0.5
    clearance_gap: float = 0.5
    rows: int = 20
    columns: int = 30
    drape_curvature: float = 0.3
    scale_height_ratio: float = 1.5
    scale_every_row: bool = False


class HybridMeshBuilder(RingMeshBuilder):
    """The 4-in-1 ring mesh with scales fused onto its rings.

    Backs both scale link types: `pyramid` puts a scale on every ring,
    `hybrid` on alternating rows.

    Scales cannot interlink - only rings can - so a sheet of nothing but scales
    is a tray of loose parts, and a mesh that alternated ring rows with scale
    rows would fall apart along every scale row. Real scalemail hangs the scales
    from rings instead, so that is what this does: the ring lattice is untouched
    and keeps its four-way linkage, and each scale rides on its ring's wire as
    one rigid printed body with it.
    """

    def __init__(self, config: HybridMeshConfig):
        super().__init__(RingMeshConfig(
            outer_diameter=config.outer_diameter, tube_radius=config.tube_radius,
            clearance_gap=config.clearance_gap, rows=config.rows, columns=config.columns,
            drape_curvature=config.drape_curvature))
        self.hybrid_config = config

    def scale_base_size(self):
        # Sized to the ring's hole so a scale never reaches its neighbours.
        return 2 * (self.centerline_radius - self.config.tube_radius)

    def has_scale(self, row):
        return True if self.hybrid_config.scale_every_row else row % 2 == 1

    def make_scale(self, row):
        """A scale riding just outside its ring, joined to the wire by a lug.

        The scale sits clear of the hole - four neighbouring wires pass through
        it and a scale lying across it would foul them - so it needs the lug to
        hold on. Without it the scale is a loose part in the print.
        """
        base = self.scale_base_size()
        normal = ring_normal(row, self.config.tilt_degrees)
        rotation = trimesh.geometry.align_vectors([0.0, 0.0, 1.0], normal)
        scale = make_pyramid(base, base * self.hybrid_config.scale_height_ratio / 2)
        scale.apply_transform(rotation)
        # Push it clear of the hole, along the ring's plane, then lug it back on.
        along = np.cross(normal, [1.0, 0.0, 0.0])
        along = along / np.linalg.norm(along)
        seat = along * self.centerline_radius
        scale.apply_translation(seat + along * base / 2 - normal * self.config.tube_radius)
        lug = trimesh.creation.cylinder(
            radius=self.config.tube_radius,
            segment=[seat - along * self.config.tube_radius,
                     seat + along * base / 2 - normal * self.config.tube_radius])
        return trimesh.util.concatenate([scale, lug])

    def generate(self):
        self.validate_linkable()
        c = self.config
        parts = []
        self._anchor_points = []
        for row in range(c.rows):
            for col in range(c.columns):
                center = self.ring_center(row, col)
                ring = self.make_ring(row)
                ring.apply_translation(center)
                parts.append(ring)
                if self.has_scale(row):
                    scale = self.make_scale(row)
                    scale.apply_translation(center)
                    parts.append(scale)
                if row == 0:
                    self._anchor_points.append(center)
        return trimesh.util.concatenate(parts)
