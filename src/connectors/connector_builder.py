from dataclasses import dataclass
import numpy as np
import trimesh
from ..mesh.torus import make_torus

CONNECTOR_TYPES = ("loop_hinge", "socket_peg", "fused_row")


@dataclass
class ConnectorConfig:
    type: str = "loop_hinge"
    loop_tube_radius: float = 1.2
    peg_diameter: float = 3.0
    peg_height: float = 2.0
    fused_bar_radius: float = 1.5


class ConnectorBuilder:
    """Joins a solid panel to the fabric.

    The connector's ring is a ring of the fabric's own lattice, one row before
    the first - so it threads rows 0's rings exactly the way a real neighbouring
    row would, and is held by the same geometry the fabric is verified against.
    A stem then runs from that ring out to the panel edge, so the finished part
    is fused to the panel at one end and linked through the fabric at the other.
    """

    def __init__(self, config: ConnectorConfig):
        self.config = config

    def resample_edge_to_anchors(self, edge_curve, anchor_points):
        n = len(anchor_points)
        idx = np.linspace(0, len(edge_curve) - 1, n).astype(int)
        return edge_curve[idx]

    def edge_points_for_sites(self, edge_curve, sites):
        """The point on the panel edge nearest each link site.

        Spreading the sites evenly along the whole edge instead would tie a ring
        in the middle of the fabric to a point at the far end of the panel
        whenever the fabric is narrower than the bag, which is the long-stem
        failure this replaced.
        """
        edge = np.asarray(edge_curve, float)
        centers = np.array([np.asarray(c, float) for c, _ in sites])
        distances = np.linalg.norm(centers[:, None, :] - edge[None, :, :], axis=2)
        return edge[distances.argmin(axis=1)]

    def link_ring(self, center, normal, outer_diameter, tube_radius):
        ring = make_torus(outer_diameter, tube_radius)
        ring.apply_transform(trimesh.geometry.align_vectors([0.0, 0.0, 1.0], normal))
        ring.apply_translation(center)
        return ring

    def stem(self, center, normal, edge_point, outer_diameter):
        """A bar from the rim of the link ring to the panel edge.

        It leaves from the rim rather than the centre so it never crosses the
        ring's hole, which has to stay clear for the fabric to swing, and it
        leaves from the side facing the panel so the stem is as short as the
        assembly allows.
        """
        radius = outer_diameter / 2 - self.config.loop_tube_radius
        center = np.asarray(center, float)
        target = np.asarray(edge_point, float)
        toward = target - center
        normal = np.asarray(normal, float)
        toward = toward - normal * np.dot(toward, normal)   # keep it in the ring's plane
        if np.linalg.norm(toward) < 1e-9:
            toward = np.array([0.0, -1.0, 0.0])
        rim = center + toward / np.linalg.norm(toward) * radius
        if np.linalg.norm(target - rim) < 1e-9:
            return None
        return trimesh.creation.cylinder(radius=self.config.loop_tube_radius,
                                         segment=[rim, target])

    def build_parts(self, edge_curve, fabric_builder, sites=None):
        """One fused (link ring + stem) body per link site.

        `sites` lets the caller pass link sites already carried into the bag
        frame; without it the fabric's own untransformed sites are used.
        """
        sites = fabric_builder.link_sites() if sites is None else sites
        od = fabric_builder.config.outer_diameter
        tr = fabric_builder.config.tube_radius
        edge_points = self.edge_points_for_sites(edge_curve, sites)
        parts = []
        for (center, normal), edge_point in zip(sites, edge_points):
            pieces = [self.link_ring(center, normal, od, tr)]
            stem = self.stem(center, normal, edge_point, od)
            if stem is not None:
                pieces.append(stem)
            parts.append(pieces)
        return parts

    def build_loop_hinges(self, parts):
        return trimesh.boolean.union([p for group in parts for p in group], engine="manifold")

    def build_socket_pegs(self, parts, edge_points):
        pieces = [p for group in parts for p in group]
        for point in edge_points:
            peg = trimesh.creation.cylinder(radius=self.config.peg_diameter / 2,
                                            height=self.config.peg_height)
            peg.apply_translation(np.asarray(point, float)
                                  + np.array([0, 0, self.config.peg_height / 2]))
            pieces.append(peg)
        return trimesh.boolean.union(pieces, engine="manifold")

    def build_fused_row(self, parts, edge_points):
        """Every stem tied together by one continuous bar along the panel edge."""
        pieces = [p for group in parts for p in group]
        radius = self.config.fused_bar_radius
        for start, end in zip(edge_points[:-1], edge_points[1:]):
            if np.linalg.norm(np.asarray(end) - np.asarray(start)) < 1e-9:
                continue
            pieces.append(trimesh.creation.cylinder(radius=radius, segment=[start, end]))
        for point in edge_points:
            joint = trimesh.creation.icosphere(subdivisions=1, radius=radius)
            joint.apply_translation(point)
            pieces.append(joint)
        return trimesh.boolean.union(pieces, engine="manifold")

    def build(self, edge_curve, fabric_builder, sites=None):
        sites = fabric_builder.link_sites() if sites is None else sites
        parts = self.build_parts(edge_curve, fabric_builder, sites)
        edge_points = self.edge_points_for_sites(edge_curve, sites)
        if self.config.type == "loop_hinge":
            return self.build_loop_hinges(parts)
        if self.config.type == "socket_peg":
            return self.build_socket_pegs(parts, edge_points)
        if self.config.type == "fused_row":
            return self.build_fused_row(parts, edge_points)
        raise ValueError(f"Unknown connector.type {self.config.type!r}; "
                         f"expected one of {', '.join(CONNECTOR_TYPES)}")
