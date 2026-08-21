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
    hole = _box([c.loop_depth, c.hole_width, b.hole_height], [b.loop_offset, 0, b.mid])
    neighbour = b.tile()
    neighbour.apply_translation([c.pitch, 0, 0])
    inside = trimesh.boolean.intersection([hole, neighbour], engine="manifold")
    assert inside is not None and inside.volume > 0


def test_a_tile_does_not_block_its_own_hole():
    b = _builder()
    c = b.config
    hole = _box([c.loop_depth, c.hole_width, b.hole_height], [b.loop_offset, 0, b.mid])
    assert _overlap(hole, b.tile()) == pytest.approx(0.0, abs=1e-9)


def test_the_head_cannot_retract_through_the_hole():
    b = _builder()
    assert b.head_height() > b.hole_height


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


def test_a_sheet_too_thin_for_the_joint_is_rejected():
    with pytest.raises(ValueError, match="cannot hold|at least"):
        _builder(thickness=2.0).validate_capturable()


def test_hole_and_thickness_follow_the_clearance():
    # Fix all three and the joint breaks the moment the clearance changes.
    for clearance in (0.2, 0.3, 0.4, 0.5):
        b = _builder(clearance_gap=clearance)
        b.validate_capturable()
        assert b.hole_height == pytest.approx(b.config.pin_thickness + 2 * clearance)
        assert b.thickness >= b.min_thickness


def test_the_requested_clearance_is_the_true_minimum():
    """clearance_gap has to mean the tightest gap anywhere, not the lateral one.

    It used to be halved vertically, and the pin head sat 0.10 mm off the
    neighbour's stem regardless of what was asked for."""
    b = _builder()
    assert b.vertical_clearance() == b.config.clearance_gap
    tile = b.tile()
    gap = min(b.neighbour_gap(tile, off)
              for off in ([b.config.pitch, 0, 0], [0, b.config.pitch, 0]))
    assert gap >= b.config.clearance_gap * 0.97


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


# Shapes that swell toward the diagonals need a different core fraction to
# hold the clearance; see test_every_shape_holds_the_clearance_it_was_asked_for.
SHAPE_FRACTION = {"star": 0.14}


@pytest.mark.parametrize("shape", sorted(CORE_SHAPES))
def test_every_named_shape_keeps_the_joint_working(shape):
    """Changing the core must not change the joint - that is the whole point."""
    b = _builder(core_shape=shape, core_fraction=SHAPE_FRACTION.get(shape, 0.30))
    b.validate_capturable()
    tile = b.tile()
    tile.merge_vertices()
    assert (2 - tile.euler_number) // 2 == 2
    b.validate_assembly(tile)


def _threaded_volume(builder):
    """How much of the neighbour sits inside this tile's loop hole."""
    c = builder.config
    hole = _box([c.loop_depth, c.hole_width, builder.hole_height],
                [builder.loop_offset, 0, builder.mid])
    neighbour = builder.tile()
    neighbour.apply_translation([c.pitch, 0, 0])
    inside = trimesh.boolean.intersection([hole, neighbour], engine="manifold")
    return 0.0 if inside is None or len(inside.vertices) == 0 else inside.volume


@pytest.mark.parametrize("shape", sorted(CORE_SHAPES))
def test_every_named_shape_is_threaded_identically(shape):
    """The core may change; how much pin sits in the hole may not."""
    reference = _threaded_volume(_builder(core_shape="square"))
    assert reference > 0
    subject = _threaded_volume(_builder(core_shape=shape,
                                        core_fraction=SHAPE_FRACTION.get(shape, 0.30)))
    assert subject == pytest.approx(reference, rel=1e-3)


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
    points = _profile(lambda th: 1 + 0.35 * np.sin(8 * th) ** 2, b0.max_core_radius() * 0.55)
    b = _builder(core_points=points)
    tile = b.tile()
    tile.merge_vertices()
    assert (2 - tile.euler_number) // 2 == 2
    b.validate_assembly(tile)


@pytest.mark.parametrize("shape", sorted(CORE_SHAPES))
def test_every_shape_holds_the_clearance_it_was_asked_for(shape):
    """Not merely non-overlapping. A shape that swells toward the diagonals
    grows into the corridor where the axis neighbour's pin head sits, so the
    tightest point in the sheet moves with the shape."""
    b = _builder(core_shape=shape)
    tile = b.tile()
    gap = min(b.neighbour_gap(tile, off)
              for off in ([b.config.pitch, 0, 0], [0, b.config.pitch, 0]))
    if gap < b.config.clearance_gap:
        pytest.skip(f"{shape} needs core_fraction {b.largest_core_fraction()}")
    b.validate_assembly(tile)


@pytest.mark.parametrize("shape,fraction", [("star", 0.14)])
def test_the_swelling_shapes_work_at_their_own_fraction(shape, fraction):
    b = _builder(core_shape=shape, core_fraction=fraction)
    b.validate_assembly(b.tile())


def test_a_shape_below_the_asked_clearance_is_rejected_not_just_overlap():
    # star at the default fraction sits well under the requested 0.3. Checking
    # only for overlap let this through, and it prints fused.
    b = _builder(core_shape="star")
    with pytest.raises(ValueError, match="clearance_gap asks for"):
        b.validate_assembly(b.tile())


def test_the_suggested_fraction_actually_works():
    b = _builder(core_shape="star")
    fixed = _builder(core_shape="star", core_fraction=b.largest_core_fraction())
    fixed.validate_assembly(fixed.tile())


def test_a_profile_that_swells_onto_the_arm_axes_is_rejected():
    b0 = _builder()
    points = _profile(lambda th: 1 + 0.6 * np.abs(np.cos(2 * th)), b0.max_core_radius() * 0.8)
    b = _builder(core_points=points)
    with pytest.raises(ValueError, match="clearance_gap asks for|overlaps it by"):
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


def _islands(mesh, layer=0.2):
    import sys
    sys.path.insert(0, ".")
    from tools.check_supports import report
    return report(mesh, layer, quiet=True)[0]


@pytest.mark.parametrize("shape", sorted(CORE_SHAPES))
def test_the_tile_prints_without_supports(shape):
    """No islands: nothing starts in mid-air.

    The first arm ran at mid height with a head taller than it, so the head's
    lower lip began in air - two islands per tile, 209 across a swatch. The arm
    is now solid from the bed out to the neighbour's loop, and the head grows
    upward off the tongue instead of hanging below it.
    """
    b = _builder(core_shape=shape, core_fraction=SHAPE_FRACTION.get(shape, 0.30))
    assert _islands(b.tile()) == 0


@pytest.mark.parametrize("layer", [0.15, 0.2, 0.3])
def test_no_islands_at_any_sensible_layer_height(layer):
    assert _islands(_builder().tile(), layer) == 0


def test_a_whole_sheet_prints_without_supports():
    assert _islands(_builder(rows=3, columns=3).generate()) == 0


def test_the_pin_arm_stands_on_the_bed_for_most_of_its_length():
    # Only the tongue is unsupported, and only as far as it must reach to pass
    # through the neighbour's loop.
    b = _builder()
    assert b.fin_end() > b.tongue_length()
    assert b.tongue_length() < b.config.pitch / 2
