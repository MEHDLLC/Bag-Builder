from dataclasses import dataclass
import numpy as np
import trimesh


@dataclass
class PyramidMeshConfig:
    base_size: float = 6.0
    height: float = 3.0
    clearance_gap: float = 0.4
    rows: int = 20
    columns: int = 30


def make_pyramid(base_size, height):
    h = base_size / 2
    verts = np.array([[-h, -h, 0], [h, -h, 0], [h, h, 0], [-h, h, 0], [0, 0, height]])
    faces = np.array([[0, 1, 2], [0, 2, 3], [0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4]])
    return trimesh.Trimesh(vertices=verts, faces=faces, process=True)


class PyramidMeshBuilder:
    def __init__(self, config: PyramidMeshConfig):
        self.config = config
        self._anchor_points = []

    def anchor_points(self):
        return self._anchor_points

    def generate(self):
        c = self.config
        spacing = c.base_size + c.clearance_gap
        parts = []
        self._anchor_points = []
        for row in range(c.rows):
            y = row * spacing * 0.5
            offset = (spacing / 2) if row % 2 else 0.0
            flip = row % 2 == 1
            for col in range(c.columns):
                x = col * spacing + offset
                pyr = make_pyramid(c.base_size, c.height)
                if flip:
                    pyr.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0]))
                    pyr.apply_translation([x, y, c.height])
                else:
                    pyr.apply_translation([x, y, 0])
                parts.append(pyr)
                if row == 0:
                    self._anchor_points.append(np.array([x, y, 0]))
        return trimesh.util.concatenate(parts)
