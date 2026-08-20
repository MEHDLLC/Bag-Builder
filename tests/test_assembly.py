import numpy as np
import pytest
from src.pipeline import assembly
from src.pipeline.generate import _build_fabric, _build_solids, _fit_counts

BODY = {"width": 300, "height": 220, "depth": 90}
THICKNESS = 3.0


def _placed():
    mesh, builder = _build_fabric({"link_type": "ring", "rows": 6, "columns": 6})
    solids, _, _ = _build_solids(BODY, {})
    placed, transforms = assembly.place(mesh, solids, BODY, THICKNESS, THICKNESS)
    return placed, transforms, builder


def test_every_part_lands_inside_the_bag_envelope():
    # The whole defect: parts were generated in unrelated frames, on top of
    # each other, so nothing could be assembled.
    placed, _, _ = _placed()
    for name, mesh in placed.items():
        lo, hi = mesh.bounds
        assert lo[0] >= -BODY["width"] / 2 - 1e-6, name
        assert hi[0] <= BODY["width"] / 2 + 1e-6, name
        assert lo[1] >= -BODY["depth"] / 2 - 1e-6, name
        assert hi[1] <= BODY["depth"] / 2 + 1e-6, name
        assert lo[2] >= -1e-6, name


def test_end_panels_stand_at_both_ends():
    placed, _, _ = _placed()
    left, right = placed["end_panel_left"], placed["end_panel_right"]
    assert left.bounds[0][0] == pytest.approx(-BODY["width"] / 2)
    assert right.bounds[1][0] == pytest.approx(BODY["width"] / 2)
    for panel in (left, right):
        assert panel.bounds[1][2] == pytest.approx(BODY["height"], abs=1e-6)


def test_fabric_walls_face_each_other_across_the_depth():
    placed, _, _ = _placed()
    front, back = placed["fabric_front"], placed["fabric_back"]
    assert front.bounds[0][1] == pytest.approx(-BODY["depth"] / 2)
    assert back.bounds[1][1] == pytest.approx(BODY["depth"] / 2)
    assert front.bounds[1][1] < back.bounds[0][1]


def test_fabric_sits_on_the_bottom_panel():
    placed, _, _ = _placed()
    for wall in ("fabric_front", "fabric_back"):
        assert placed[wall].bounds[0][2] == pytest.approx(THICKNESS)


def test_link_sites_follow_their_wall():
    _, transforms, builder = _placed()
    sites = builder.link_sites()
    moved = assembly.transform_sites(sites, transforms["fabric_front"])
    assert len(moved) == len(sites)
    # Normals are rotated, not left pointing the sheet's original way.
    assert not np.allclose([n for _, n in moved], [n for _, n in sites])


def test_connector_stem_is_a_short_real_distance():
    """It used to span an artefact of the broken layout - over 100mm."""
    _, transforms, builder = _placed()
    moved = assembly.transform_sites(builder.link_sites(), transforms["fabric_front"])
    from src.connectors.connector_builder import ConnectorBuilder, ConnectorConfig
    edge = assembly.bottom_panel_edge(BODY, "front", THICKNESS)
    points = ConnectorBuilder(ConnectorConfig()).edge_points_for_sites(edge, moved)
    spans = [np.linalg.norm(np.asarray(c) - p) for (c, _), p in zip(moved, points)]
    assert max(spans) < 4 * builder.config.outer_diameter


def test_fit_body_counts_fill_the_wall_without_overshooting():
    cfg = {"ring_outer_diameter": 16.0, "ring_tube_radius": 1.0}
    rows, columns = _fit_counts(cfg, BODY, THICKNESS)
    _, builder = _build_fabric({**cfg, "rows": rows, "columns": columns})
    covers = assembly.wall_coverage(BODY, builder, THICKNESS)["covers"]
    assert min(covers) >= 0.9      # actually fills the wall
    assert max(covers) <= 1.0      # a sheet that overshoots hangs off the bag
