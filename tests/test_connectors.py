import networkx as nx
import numpy as np
import pytest
from src.connectors.connector_builder import ConnectorBuilder, ConnectorConfig
from src.mesh.ring_mesh import RingMeshConfig, RingMeshBuilder, ring_normal
from src.mesh.interlink import is_linked

# A panel edge running above and behind the fabric, as edge_curve("top") gives.
EDGE = np.array([[float(x) * 2, -12.0, 3.0] for x in range(12)])


def _fabric(rows=4, columns=4):
    builder = RingMeshBuilder(RingMeshConfig(rows=rows, columns=columns, drape_curvature=0.0))
    builder.generate()
    return builder


def _body_count(mesh):
    # trimesh's own body_count wants scipy, which this project does not depend
    # on; networkx is already required for 3mf export.
    graph = nx.Graph()
    graph.add_nodes_from(range(len(mesh.faces)))
    graph.add_edges_from(mesh.face_adjacency)
    return nx.number_connected_components(graph)


def _build(conn_type, fabric=None):
    fabric = fabric or _fabric()
    return ConnectorBuilder(ConnectorConfig(type=conn_type)).build(EDGE, fabric)


@pytest.mark.parametrize("conn_type", ["loop_hinge", "socket_peg", "fused_row"])
def test_every_connector_type_emits_geometry(conn_type):
    mesh = _build(conn_type)
    assert len(mesh.vertices) > 0
    assert len(mesh.faces) > 0


@pytest.mark.parametrize("conn_type", ["loop_hinge", "socket_peg", "fused_row"])
def test_every_connector_actually_threads_the_fabric(conn_type):
    """The whole point: the solid part has to be linked to the mesh part."""
    fabric = _fabric()
    radius = fabric.centerline_radius
    tilt = fabric.config.tilt_degrees
    sites = fabric.link_sites()
    for site_center, site_normal in sites:
        linked = any(
            is_linked(site_center, site_normal, fabric.ring_center(0, c),
                      ring_normal(0, tilt), radius)
            for c in range(fabric.config.columns))
        assert linked


@pytest.mark.parametrize("conn_type", ["loop_hinge", "socket_peg", "fused_row"])
def test_every_connector_reaches_the_panel_edge(conn_type):
    """...and fused to the panel at the other end, or it is just a loose ring."""
    mesh = _build(conn_type)
    assert mesh.bounds[0][1] <= EDGE[:, 1].min() + 1e-6


def test_fused_row_is_one_solid():
    assert _body_count(_build("fused_row")) == 1


def test_loop_hinge_is_one_body_per_link_site():
    fabric = _fabric()
    assert _body_count(_build("loop_hinge", fabric)) == len(fabric.link_sites())


def test_unknown_connector_type_raises():
    with pytest.raises(ValueError, match="Unknown connector.type"):
        _build("magnets")
