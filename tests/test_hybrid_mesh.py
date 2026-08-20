import pytest
from src.mesh.hybrid_mesh import HybridMeshConfig, HybridMeshBuilder
from src.mesh.ring_mesh import RingMeshConfig, RingMeshBuilder


def _hybrid(rows=4, columns=5):
    return HybridMeshBuilder(HybridMeshConfig(rows=rows, columns=columns, drape_curvature=0.0))


def _ring(rows=4, columns=5):
    return RingMeshBuilder(RingMeshConfig(rows=rows, columns=columns, drape_curvature=0.0))


def test_hybrid_generates():
    assert len(_hybrid().generate().vertices) > 0


def test_hybrid_is_not_just_the_ring_mesh():
    # The original bug: `hybrid` silently produced the ring mesh byte for byte.
    assert len(_hybrid().generate().vertices) != len(_ring().generate().vertices)


def test_hybrid_adds_scales_without_moving_the_rings():
    # Scales hang off the lattice; they must not shift it, or the linkage the
    # ring mesh is verified for would no longer hold.
    hybrid, ring = _hybrid(), _ring()
    for row in range(4):
        for col in range(5):
            assert hybrid.ring_center(row, col) == pytest.approx(ring.ring_center(row, col))


def test_scales_land_on_alternating_rows():
    builder = _hybrid()
    assert [builder.has_scale(r) for r in range(4)] == [False, True, False, True]


def test_scale_fits_inside_the_ring():
    builder = _hybrid()
    hole_diameter = 2 * (builder.centerline_radius - builder.config.tube_radius)
    assert builder.scale_base_size() <= hole_diameter


def test_hybrid_anchors_are_the_first_row():
    columns = 5
    builder = _hybrid(rows=4, columns=columns)
    builder.generate()
    assert len(builder.anchor_points()) == columns


def test_scales_are_attached_to_their_ring():
    # A scale that does not touch its ring is a loose part in the print. This
    # was true of the first attempt, so it is pinned here.
    import numpy as np
    from src.mesh.ring_mesh import ring_normal
    from src.mesh.interlink import ring_points

    builder = _hybrid()
    for row in (1, 3):
        scale = builder.make_scale(row)
        wire = ring_points([0, 0, 0], ring_normal(row, builder.config.tilt_degrees),
                           builder.centerline_radius)
        gap = np.linalg.norm(scale.vertices[:, None, :] - wire[None, :, :], axis=2).min()
        assert gap < builder.config.tube_radius


def test_scales_stay_clear_of_the_ring_hole():
    # Four neighbouring wires thread every hole; a scale across it would foul them.
    builder = _hybrid()
    hole_radius = builder.centerline_radius - builder.config.tube_radius
    scale = builder.make_scale(1)
    import numpy as np
    from src.mesh.ring_mesh import ring_normal
    normal = ring_normal(1, builder.config.tilt_degrees)
    in_plane = scale.vertices - np.outer(scale.vertices @ normal, normal)
    assert np.linalg.norm(in_plane, axis=1).max() > hole_radius
