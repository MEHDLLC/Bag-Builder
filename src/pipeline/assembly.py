"""Places the generated parts into one bag coordinate frame.

Every builder works in its own convenient frame - panels come out flat in XY,
the fabric grows away from the origin - and nothing used to reconcile them, so
the parts were generated on top of each other and the connector spanned a
distance that was an artefact of that rather than a real dimension.

The bag frame is:

    x   width, -W/2 .. W/2      the long axis
    y   depth, -D/2 .. D/2
    z   height, 0 .. H          z=0 is the underside of the bottom panel

Which edge of the fabric can carry a connector is decided by the lattice, not by
preference: in European 4-in-1 links only ever run between adjacent *rows*, so a
sheet can be joined along a horizontal row. A vertical column edge has no
lattice position that links it, which is why the fabric hangs from its bottom
row rather than being seamed up the sides.
"""
import numpy as np
import trimesh

# Maps a part's own (x, y, z) to (z, x, y): the profile's width becomes bag
# depth and its height becomes bag height, standing a flat panel up on end.
_STAND_UP = trimesh.transformations.rotation_matrix(2 * np.pi / 3, [1.0, 1.0, 1.0])
# Maps (x, y, z) to (x, -z, y): tips a flat fabric sheet up into a wall.
_TIP_UP = trimesh.transformations.rotation_matrix(np.pi / 2, [1.0, 0.0, 0.0])


def _transformed(mesh, matrix):
    out = mesh.copy()
    out.apply_transform(matrix)
    return out


def _translation(offset):
    return trimesh.transformations.translation_matrix(offset)


def end_panel_matrix(side, width, height, thickness):
    """Stand an end panel on end at x = -W/2 (left) or +W/2 (right)."""
    x = -width / 2 if side == "left" else width / 2 - thickness
    return _translation([x, 0.0, height / 2]) @ _STAND_UP


def fabric_wall_matrix(side, depth, fabric_bounds, base_z):
    """Tip a fabric sheet up into the front (-y) or back (+y) wall.

    The sheet is centred across the bag width and its lowest row is set on top
    of the bottom panel, so the row the connector attaches to sits where the
    bottom panel edge actually is.
    """
    tipped_lo, tipped_hi = fabric_bounds
    x_shift = -(tipped_lo[0] + tipped_hi[0]) / 2
    # Both walls sit inside the bag: the front wall's outer face on -D/2, the
    # back wall's outer face on +D/2, so neither hangs off the body.
    if side == "front":
        y_shift = -depth / 2 - tipped_lo[1]
    else:
        y_shift = depth / 2 - tipped_hi[1]
    return _translation([x_shift, y_shift, base_z - tipped_lo[2]]) @ _TIP_UP


def wall_coverage(body_cfg, fabric_builder, bottom_thickness):
    """How much of the bag wall the configured rows and columns actually cover."""
    width = body_cfg.get("width", 300)
    height = body_cfg.get("height", 220)
    cfg = fabric_builder.config
    spans_x = cfg.columns * fabric_builder.column_pitch()
    spans_z = cfg.rows * fabric_builder.row_pitch()
    opening = max(height - bottom_thickness, 1e-9)
    return {
        "wall_mm": [round(width, 2), round(opening, 2)],
        "fabric_mm": [round(spans_x, 2), round(spans_z, 2)],
        "covers": [round(spans_x / width, 3), round(spans_z / opening, 3)],
        "columns_to_fill": int(np.floor(width / fabric_builder.column_pitch())),
        "rows_to_fill": int(np.floor(opening / fabric_builder.row_pitch())),
    }


def transform_sites(sites, matrix):
    """Carry (centre, normal) link sites through a placement transform."""
    rotation = matrix[:3, :3]
    moved = []
    for center, normal in sites:
        placed = trimesh.transformations.transform_points(
            np.asarray(center, float).reshape(1, 3), matrix)[0]
        moved.append((placed, rotation @ np.asarray(normal, float)))
    return moved


def place(fabric_mesh, solids, body_cfg, panel_thickness, bottom_thickness):
    """Return the placed parts plus the transform each fabric wall received."""
    width = body_cfg.get("width", 300)
    height = body_cfg.get("height", 220)
    depth = body_cfg.get("depth", 90)

    placed = {"bottom_panel": solids["bottom_panel"]}
    for side, name in (("left", "end_panel_left"), ("right", "end_panel_right")):
        matrix = end_panel_matrix(side, width, height, panel_thickness)
        placed[name] = _transformed(solids[name], matrix)

    tipped = _transformed(fabric_mesh, _TIP_UP)
    transforms = {}
    for side, name in (("front", "fabric_front"), ("back", "fabric_back")):
        matrix = fabric_wall_matrix(side, depth, tipped.bounds, bottom_thickness)
        placed[name] = _transformed(fabric_mesh, matrix)
        transforms[name] = matrix
    return placed, transforms


def bottom_panel_edge(body_cfg, side, bottom_thickness, samples=64):
    """The long edge of the bottom panel that a fabric wall is joined to."""
    width = body_cfg.get("width", 300)
    depth = body_cfg.get("depth", 90)
    y = -depth / 2 if side == "front" else depth / 2
    x = np.linspace(-width / 2, width / 2, samples)
    return np.column_stack([x, np.full(samples, y), np.full(samples, bottom_thickness)])
