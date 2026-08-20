import numpy as np
import pytest
from src.mesh.ring_mesh import RingMeshConfig, RingMeshBuilder, ring_normal
from src.mesh.hybrid_mesh import HybridMeshConfig, HybridMeshBuilder
from src.mesh.interlink import is_linked, surface_gap, lattice_report


def _builder(**kw):
    cfg = RingMeshConfig(rows=5, columns=5, drape_curvature=0.0, **kw)
    return RingMeshBuilder(cfg)


def test_interior_rings_link_exactly_four_neighbours():
    builder = _builder()
    builder.generate()
    counts, _ = lattice_report(builder)
    interior = [n for (r, c), n in counts.items()
                if 0 < r < builder.config.rows - 1 and 0 < c < builder.config.columns - 1]
    assert interior, "no interior rings to check"
    assert set(interior) == {4}


def test_no_two_rings_interpenetrate():
    builder = _builder()
    builder.generate()
    _, worst = lattice_report(builder)
    assert worst >= builder.config.clearance_gap


def test_no_ring_floats_free():
    # Corner rings legitimately have a single link - that is what the edge of a
    # 4-in-1 sheet looks like - but a ring with none is a loose ring in a bag.
    builder = _builder()
    builder.generate()
    counts, _ = lattice_report(builder)
    assert min(counts.values()) >= 1
    assert sum(1 for n in counts.values() if n == 1) <= 2


def test_connector_link_sites_thread_the_first_row():
    builder = _builder()
    builder.generate()
    radius = builder.centerline_radius
    tilt = builder.config.tilt_degrees
    for site_center, site_normal in builder.link_sites():
        linked = [c for c in range(builder.config.columns)
                  if is_linked(site_center, site_normal,
                               builder.ring_center(0, c), ring_normal(0, tilt), radius)]
        assert linked, "a connector ring hangs free of the fabric"


def test_clearance_scales_with_ring_size():
    small = _builder(outer_diameter=8.0, tube_radius=0.5)
    large = _builder(outer_diameter=16.0, tube_radius=1.0)
    small.generate()
    large.generate()
    assert lattice_report(large)[1] > lattice_report(small)[1]


def test_hybrid_keeps_the_ring_linkage():
    # Scales ride on the rings; they must not disturb the lattice.
    hybrid = HybridMeshBuilder(HybridMeshConfig(rows=5, columns=5, drape_curvature=0.0))
    hybrid.generate()
    counts, _ = lattice_report(hybrid)
    interior = [n for (r, c), n in counts.items() if 0 < r < 4 and 0 < c < 4]
    assert set(interior) == {4}


def test_a_fat_wire_in_a_small_ring_is_rejected():
    # This was the old default: outer diameter 8 with a 1.0 tube radius cannot
    # interlink, and used to silently produce a fused slab.
    builder = _builder(outer_diameter=8.0, tube_radius=1.0)
    with pytest.raises(ValueError, match="aspect ratio"):
        builder.generate()


def test_parallel_rings_can_never_link():
    # The reason rows have to alternate their lean.
    n = np.array([0.0, 0.0, 1.0])
    assert not is_linked([0, 0, 0], n, [3.0, 0, 0], n, 3.5)


@pytest.mark.parametrize("curvature", [0.0, 0.1, 0.3, 0.6, 1.0])
def test_drape_does_not_break_the_lattice(curvature):
    """Drape has to bend the sheet, not shear it.

    Every interlink test used to pin curvature to zero, so nobody noticed that
    the shipped default of 0.3 dropped some rings to two links and that 0.1-0.2
    drove neighbouring rings into each other hard enough to fuse.
    """
    builder = RingMeshBuilder(RingMeshConfig(rows=5, columns=5, drape_curvature=curvature))
    builder.generate()
    counts, worst = lattice_report(builder)
    interior = [n for (r, c), n in counts.items() if 0 < r < 4 and 0 < c < 4]
    assert set(interior) == {4}
    assert worst >= builder.config.clearance_gap


def test_drape_actually_curves_the_sheet():
    flat = RingMeshBuilder(RingMeshConfig(rows=8, columns=3, drape_curvature=0.0)).generate()
    bent = RingMeshBuilder(RingMeshConfig(rows=8, columns=3, drape_curvature=0.8)).generate()
    span = lambda m: m.bounds[1][2] - m.bounds[0][2]
    assert span(bent) > span(flat)


def test_rows_stay_one_pitch_apart_along_the_draped_surface():
    """The property that makes drape safe: bending moves rows along the surface,
    it does not change how far apart they are on it."""
    builder = RingMeshBuilder(RingMeshConfig(rows=8, columns=3, drape_curvature=0.8))
    # Only the y-z components: x carries the half-pitch stagger of odd rows.
    surface = [builder.ring_center(r, 0)[1:] for r in range(8)]
    steps = [np.linalg.norm(b - a) for a, b in zip(surface, surface[1:])]
    assert all(s == pytest.approx(builder.row_pitch(), rel=0.02) for s in steps)
