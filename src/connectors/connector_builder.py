from dataclasses import dataclass
import numpy as np
import trimesh
from ..mesh.torus import make_torus


@dataclass
class ConnectorConfig:
    type: str = "loop_hinge"
    loop_tube_radius: float = 1.2
    peg_diameter: float = 3.0
    peg_height: float = 2.0


class ConnectorBuilder:
    def __init__(self, config: ConnectorConfig):
        self.config = config

    def resample_edge_to_anchors(self, edge_curve, anchor_points):
        n = len(anchor_points)
        idx = np.linspace(0, len(edge_curve) - 1, n).astype(int)
        return edge_curve[idx]

    def build_loop_hinges(self, points):
        parts = []
        for p in points:
            loop = make_torus(self.config.loop_tube_radius * 4, self.config.loop_tube_radius, u_seg=16, v_seg=8)
            loop.apply_translation(p)
            parts.append(loop)
        return trimesh.util.concatenate(parts)

    def build_socket_pegs(self, points):
        parts = []
        for p in points:
            peg = trimesh.creation.cylinder(radius=self.config.peg_diameter / 2, height=self.config.peg_height)
            peg.apply_translation(p + np.array([0, 0, self.config.peg_height / 2]))
            parts.append(peg)
        return trimesh.util.concatenate(parts)

    def build(self, edge_curve, anchor_points):
        points = self.resample_edge_to_anchors(edge_curve, anchor_points)
        if self.config.type == "loop_hinge":
            return self.build_loop_hinges(points)
        if self.config.type == "socket_peg":
            return self.build_socket_pegs(points)
        return trimesh.Trimesh()
