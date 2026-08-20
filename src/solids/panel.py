from dataclasses import dataclass
import numpy as np
import trimesh


@dataclass
class PanelConfig:
    shape_profile: str = "rounded_rectangle"
    width: float = 300.0
    height: float = 220.0
    thickness: float = 3.0
    corner_radius: float = 15.0
    top_width_ratio: float = 1.0


class PanelBuilder:
    def __init__(self, config: PanelConfig):
        self.config = config

    def _profile_points(self):
        c = self.config
        w, h, r = c.width, c.height, c.corner_radius
        if c.shape_profile == "rectangular":
            return np.array([[-w/2, -h/2], [w/2, -h/2], [w/2, h/2], [-w/2, h/2]])
        if c.shape_profile == "trapezoidal":
            top_w = w * c.top_width_ratio
            return np.array([[-w/2, -h/2], [w/2, -h/2], [top_w/2, h/2], [-top_w/2, h/2]])
        pts = []
        corners = [(-w/2+r, -h/2+r, 180, 270), (w/2-r, -h/2+r, 270, 360),
                   (w/2-r, h/2-r, 0, 90), (-w/2+r, h/2-r, 90, 180)]
        for cx, cy, a0, a1 in corners:
            angles = np.radians(np.linspace(a0, a1, 6))
            pts.extend([[cx + r*np.cos(a), cy + r*np.sin(a)] for a in angles])
        return np.array(pts)

    def edge_curve(self, side="top"):
        pts2d = self._profile_points()
        c = self.config
        if side == "top":
            mask = pts2d[:, 1] > 0
        elif side == "bottom":
            mask = pts2d[:, 1] < 0
        elif side == "left":
            mask = pts2d[:, 0] < 0
        else:
            mask = pts2d[:, 0] > 0
        edge_pts = pts2d[mask]
        edge_pts = edge_pts[np.argsort(edge_pts[:, 0])]
        z = np.full((edge_pts.shape[0], 1), c.thickness)
        return np.hstack([edge_pts, z])

    def generate(self):
        pts2d = self._profile_points()
        polygon = trimesh.path.polygons.Polygon(pts2d)
        return trimesh.creation.extrude_polygon(polygon, height=self.config.thickness)
