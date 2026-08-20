import numpy as np
import pytest
import trimesh

from src.mesh.tile_mesh import CORE_SHAPES, TileMeshConfig, TileMeshBuilder, _box


def _builder(**kw):
    settings = {"rows": 3, "columns": 3, "drape_curvature": 0.0}
    settings.update(kw)
    return TileMeshBuilder(TileMeshConfig(**settings))


def _overlap(a, b):
    """Exact overlap volume. Vertex sampling misses shallow collisions."""
    hit = trimesh.boolean.intersection([a, b], engine="manifold")
    return 0.0 if hit is None or len(hit.vertices) == 0 else hit.volume


def test_tile_is_a_closed_solid_with_one_hole_per_loop():
    tile = _builder().tile()
    tile.merge_vertices()
    assert tile.is_watertight
    assert (2 - tile.euler_number) // 2 == 2


@pytest.mark.parametrize("offset", ["x", "y", "xy"])
def test_neighbouring_tiles_never_touch(offset):
    b = _builder()
    pitch = b.config.pitch
    shift = {"x": [pitch, 0, 0], "y": [0, pitch, 0], "xy": [pitch, pitch, 0]}[offset]
    tile = b.tile()
    other = tile.copy()
    other.apply_translation(shift)
    assert _overlap(tile, other) == pytest.approx(0.0, abs=1e-9)


def test_the_neighbours_pin_threads_this_tile_s_loop():
    """The whole mechanism: without this the sheet is loose tiles."""
    b = _builder()
    c = b.config
    hole = _box([c.loop_depth, c.hole_width, c.hole_height], [b.loop_offset, 0, b.mid])
    neighbour = b.tile()
    neighbour.apply_translation([c.pitch, 0, 0])
    inside = trimesh.boolean.intersection([hole, neighbour], engine="manifold")
    assert inside is not None and inside.volume > 0


def test_a_tile_does_not_block_its_own_hole():
    b = _builder()
    c = b.config
    hole = _box([c.loop_depth, c.hole_width, c.hole_height], [b.loop_offset, 0, b.mid])
    assert _overlap(hole, b.tile()) == pytest.approx(0.0, abs=1e-9)


def test_the_head_cannot_retract_through_the_hole():
    b = _builder()
    assert b.head_height() > b.config.hole_height


def test_the_head_clears_the_stem_it_locks_behind():
    b = _builder()
    assert b.mid - b.head_height() / 2 > b.config.stem_height


@pytest.mark.parametrize("clearance", [0.2, 0.3, 0.4, 0.5])
@pytest.mark.parametrize("pitch", [6.0, 7.0, 10.0])
def test_geometry_stays_buildable_across_fit_and_size(clearance, pitch):
    # Arm geometry is derived from pitch and clearance, so changing either has
    # to keep the joint possible rather than silently producing a broken tile.
    b = _builder(clearance_gap=clearance, pitch=pitch)
    b.validate_capturable()
    tile = b.tile()
    tile.merge_vertices()
    assert (2 - tile.euler_number) // 2 == 2
    other = tile.copy()
    other.apply_translation([pitch, 0, 0])
    assert _overlap(tile, other) == pytest.approx(0.0, abs=1e-9)


def test_a_hole_too_tall_to_lock_is_rejected():
    with pytest.raises(ValueError, match="lock and clear the stem"):
        _builder(hole_height=2.0).validate_capturable()


def test_a_pin_with_nowhere_to_put_its_head_is_rejected():
    with pytest.raises(ValueError, match="no room for a pin head"):
        _builder(loop_fraction=0.26).validate_capturable()


def test_too_much_drape_over_too_few_rows_is_rejected():
    # Tiles cannot take the drape a ring lattice can; this used to collide silently.
    b = TileMeshBuilder(TileMeshConfig(rows=4, columns=2, drape_curvature=0.8))
    with pytest.raises(ValueError, match="drape_curvature"):
        b.generate()


def test_the_same_curve_over_more_rows_is_fine():
    TileMeshBuilder(TileMeshConfig(rows=31, columns=2, drape_curvature=0.8)).validate_drape()


def test_sheet_generates_with_one_tile_per_lattice_point():
    b = _builder(rows=3, columns=4)
    sheet = b.generate()
    assert len(sheet.vertices) > 0
    assert len(sheet.faces) == len(b.tile().faces) * 12


@pytest.mark.parametrize("curvature", [0.0, 0.3, 0.8, 1.0])
def test_drape_does_not_collide_the_tiles(curvature):
    # A bag wall is tens of rows, which spreads the curve thinly enough.
    b = TileMeshBuilder(TileMeshConfig(rows=31, columns=2, drape_curvature=curvature))
    b.generate()
    tile = b.tile()
    for row in range(4):
        a = tile.copy()
        a.apply_transform(trimesh.transformations.rotation_matrix(b.tile_angle(row), [1, 0, 0]))
        a.apply_translation(b.tile_center(row, 0))
        c = tile.copy()
        c.apply_transform(trimesh.transformations.rotation_matrix(b.tile_angle(row + 1), [1, 0, 0]))
        c.apply_translation(b.tile_center(row + 1, 0))
        assert _overlap(a, c) == pytest.approx(0.0, abs=1e-9)


def test_link_body_is_a_tile_so_connectors_thread_the_sheet():
    b = _builder()
    body = b.link_body()
    body.merge_vertices()
    assert (2 - body.euler_number) // 2 == 2
    assert len(b.link_sites()) == b.config.columns


# --- the core profile is a variable; the joint is not -----------------------

def _profile(fn, radius, n=96):
    theta = np.linspace(0, 2 * np.pi, n, endpoint=False)
    r = radius * np.asarray(fn(theta), dtype=float)
    return tuple(map(tuple, np.column_stack([r * np.cos(theta), r * np.sin(theta)])))


@pytest.mark.parametrize("shape", sorted(CORE_SHAPES))
def test_every_named_shape_keeps_the_joint_working(shape):
    """Changing the core must not change the joint - that is the whole point."""
    b = _builder(core_shape=shape)
    b.validate_capturable()
    tile = b.tile()
    tile.merge_vertices()
    assert (2 - tile.euler_number) // 2 == 2
    b.validate_assembly(tile)


@pytest.mark.parametrize("shape", sorted(CORE_SHAPES))
def test_every_named_shape_is_threaded_identically(shape):
    b = _builder(core_shape=shape)
    c = b.config
    hole = _box([c.loop_depth, c.hole_width, c.hole_height], [b.loop_offset, 0, b.mid])
    neighbour = b.tile()
    neighbour.apply_translation([c.pitch, 0, 0])
    inside = trimesh.boolean.intersection([hole, neighbour], engine="manifold")
    assert inside is not None and inside.volume == pytest.approx(0.504, abs=1e-3)


@pytest.mark.parametrize("shape", sorted(CORE_SHAPES))
def test_shapes_are_normalised_to_the_arm_axes(shape):
    # Normalising on the axes is what makes a shape swap safe: the binding
    # direction is fixed, and only the roomy diagonals change.
    b = _builder(core_shape=shape)
    points = b.core_profile()
    assert np.linalg.norm(points[0]) == pytest.approx(b.core_radius(), rel=1e-6)


def test_shape_changes_the_area_it_covers():
    areas = {s: _builder(core_shape=s).tile().volume for s in ("diamond", "square", "star")}
    assert areas["diamond"] < areas["square"] < areas["star"]


def test_a_script_can_wire_in_its_own_formula():
    b0 = _builder()
    points = _profile(lambda th: 1 + 0.35 * np.sin(8 * th) ** 2, b0.max_core_radius() * 0.8)
    b = _builder(core_points=points)
    tile = b.tile()
    tile.merge_vertices()
    assert (2 - tile.euler_number) // 2 == 2
    b.validate_assembly(tile)


def test_a_profile_that_swells_onto_the_arm_axes_is_rejected():
    b0 = _builder()
    points = _profile(lambda th: 1 + 0.6 * np.abs(np.cos(2 * th)), b0.max_core_radius() * 0.8)
    b = _builder(core_points=points)
    with pytest.raises(ValueError, match="overlaps its"):
        b.validate_assembly(b.tile())


def test_the_core_limit_grows_with_the_core():
    # core_fraction cannot outrun its own limit: enlarging the core pushes the
    # pin further out, which moves the limit with it. The binding constraint on
    # a bigger core is the loop, not the pin.
    for fraction in (0.30, 0.36, 0.42, 0.50):
        b = _builder(core_fraction=fraction)
        assert b.core_radius() <= b.max_core_radius()


def test_an_unknown_shape_name_is_rejected():
    with pytest.raises(ValueError, match="unknown core_shape"):
        _builder(core_shape="hexadecagon").core_profile()
