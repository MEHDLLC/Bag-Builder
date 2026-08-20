"""Flat interlocking tiles - the mechanism the reference meshes use.

Not chainmail. A tile is a flat plate with four arms: two of them are *loops*
standing across the arm axis, and two are *pins* that thread the neighbouring
tile's loop. One tile shape tiles the whole sheet, because a tile's +x loop is
always met by its +x neighbour's -x pin.

Each pin ends in a head taller than the hole it passes through, so the joint
cannot be pulled apart - which only works because the sheet is printed in
place and the head never has to pass through the hole.

Why bother, when ring_mesh already makes a working fabric: the reference sheets
cost about a sixth of the triangles per square millimetre that a torus lattice
does, and every surface is a flat plate, so nothing overhangs and nothing needs
support. See docs/reference-meshes.md for the measurements.

The geometry below is laid out along +x. The +y arms are the same thing rotated
a quarter turn, so a tile connects to four neighbours.
"""
from dataclasses import dataclass

import numpy as np
import trimesh

from .ring_mesh import MAX_BEND_DEGREES, drape_frame


@dataclass
class TileMeshConfig:
    pitch: float = 7.0            # centre-to-centre spacing of tiles
    thickness: float = 2.4        # total sheet thickness
    arm_width: float = 3.0        # loop outer width, across the arm
    hole_width: float = 2.0       # the opening the pin threads
    hole_height: float = 0.9
    wall: float = 0.75            # loop wall above and below the hole
    stem_height: float = 0.4      # the bottom-layer strap carrying the loop
    loop_depth: float = 0.6       # loop thickness along the arm
    loop_fraction: float = 0.46   # loop centre as a fraction of pitch
    core_fraction: float = 0.30   # core width across the arm axes, as a fraction of pitch
    core_shape: str = "square"    # a name from CORE_SHAPES, or use core_points
    core_points: tuple = ()       # explicit (x, y) profile, overrides core_shape
    clearance_gap: float = 0.3
    rows: int = 20
    columns: int = 30
    drape_curvature: float = 0.3


def _regular(sides):
    """Radius-by-angle for a regular polygon with a vertex on the +x axis."""
    step = 2 * np.pi / sides
    def radius(theta):
        local = np.mod(theta, step) - step / 2
        return np.cos(step / 2) / np.cos(local)
    return radius


def _clover(bulge):
    """Round on the axes, swelling into the diagonals where the room is."""
    def radius(theta):
        return 1.0 + bulge * (1.0 - np.abs(np.cos(2 * theta)))
    return radius


# Every profile is normalised so its radius on the arm axes is exactly 1, then
# scaled by the room those axes actually have. That is the binding direction -
# the diagonals have several times more space - so normalising there means a
# shape swap never breaks the joint.
CORE_SHAPES = {
    "circle": lambda theta: np.ones_like(theta),
    "square": lambda theta: 1.0 / np.maximum(np.abs(np.cos(theta)), np.abs(np.sin(theta))),
    "diamond": lambda theta: 1.0 / (np.abs(np.cos(theta)) + np.abs(np.sin(theta))),
    "hexagon": _regular(6),
    "octagon": _regular(8),
    "clover": _clover(0.9),
    "star": lambda theta: 1.0 + 1.2 * np.abs(np.sin(2 * theta)) ** 3,
}


def _box(extents, center):
    box = trimesh.creation.box(extents=extents)
    box.apply_translation(center)
    return box


class TileMeshBuilder:
    def __init__(self, config: TileMeshConfig):
        self.config = config
        self._anchor_points = []

    # -- derived geometry -------------------------------------------------

    @property
    def mid(self):
        return self.config.thickness / 2

    # The arm geometry is derived from the pitch and the clearance rather than
    # given in millimetres, so a change to either stays self-consistent instead
    # of quietly making the joint impossible.

    def core_radius(self):
        """Half the core's width measured along an arm axis.

        An independent input, not derived: the pin and head are positioned
        relative to the core, so deriving the core from them would be circular.
        max_core_radius is the check on it.
        """
        return self.config.pitch * self.config.core_fraction / 2

    def max_core_radius(self):
        """How far the core may reach along an arm axis before it fouls.

        Two things bound it and the tighter one wins: the neighbour's pin tip
        coming the other way, and this tile's own loop hole, which the core
        must not block. The diagonals are far less constrained - a diagonal
        neighbour's centre is pitch*sqrt(2) away - which is why a profile that
        swells into the diagonals has room a square core does not use.
        """
        c = self.config
        pin_tip = c.pitch - self.pin_reach() - c.clearance_gap
        own_loop = self.loop_offset - c.loop_depth / 2 - c.clearance_gap
        return min(pin_tip, own_loop)

    def core_profile(self, samples=96):
        """The core's plan outline, as (x, y) points.

        This is the part of the tile that is free to change. The joint - loop,
        pin and head - is fixed, so any profile that stays inside the room the
        axes allow keeps the fabric working. Pass core_points for a shape that
        is not in CORE_SHAPES; a script can generate them from any formula.
        """
        c = self.config
        if c.core_points:
            return np.asarray(c.core_points, dtype=float)
        if c.core_shape not in CORE_SHAPES:
            raise ValueError(f"unknown core_shape {c.core_shape!r}; "
                             f"expected one of {', '.join(sorted(CORE_SHAPES))}")
        theta = np.linspace(0, 2 * np.pi, samples, endpoint=False)
        radius = np.asarray(CORE_SHAPES[c.core_shape](theta), dtype=float) * self.core_radius()
        return np.column_stack([radius * np.cos(theta), radius * np.sin(theta)])

    @property
    def core_size(self):
        """Kept as the axis-to-axis width, which is what the arms care about."""
        return 2 * self.core_radius()

    @property
    def loop_offset(self):
        return self.config.pitch * self.config.loop_fraction

    def head_room(self):
        """The gap the head has to live in: past my core, short of my loop."""
        c = self.config
        near = self.core_size / 2 + c.clearance_gap
        far = self.loop_offset - c.loop_depth / 2 - c.clearance_gap
        return near, far

    def head_length(self):
        near, far = self.head_room()
        return max((far - near) * 0.6, 0.0)

    def pin_reach(self):
        """Centre to pin tip, with the head centred in the room available."""
        near, far = self.head_room()
        slack = (far - near) - self.head_length()
        tip = near + slack / 2
        return self.config.pitch - tip

    def hole_span(self):
        half = self.config.hole_height / 2
        return self.mid - half, self.mid + half

    def pin_height(self):
        return self.config.hole_height - 2 * self.vertical_clearance()

    def head_height(self):
        """Taller than the hole, so the pin cannot retract through it.

        Sized midway between the smallest head that still locks (the hole
        height) and the tallest that still clears the neighbour's stem. Tying
        it to clearance_gap instead would couple the lock to the print fit, and
        a loose fit would push the head into the stem.
        """
        c = self.config
        return (c.hole_height + self.head_height_limit()) / 2

    def head_height_limit(self):
        """Above this the head fouls the stem of the tile it locks into."""
        return self.config.thickness - 2 * self.config.stem_height

    def vertical_clearance(self):
        return self.config.clearance_gap / 2

    def arm_reach(self):
        """Furthest a tile's arm extends from its centre."""
        return max(self.pin_reach(), self.loop_offset + self.config.loop_depth / 2)

    def bend_per_row(self):
        c = self.config
        if c.rows <= 1 or c.drape_curvature <= 0:
            return 0.0
        return np.radians(MAX_BEND_DEGREES) * c.drape_curvature / (c.rows - 1)

    def max_bend_per_row(self):
        """Beyond this, rotating a row swings its arms into its neighbour's.

        Rings tolerate drape because a ring is small next to its row pitch. A
        tile is not: its arms reach past the pitch into the neighbour, so the
        relative rotation between adjacent rows closes the clearance at the arm
        tip long before the tiles themselves would touch.
        """
        return self.config.clearance_gap / self.arm_reach()

    def validate_drape(self):
        if self.bend_per_row() > self.max_bend_per_row():
            c = self.config
            safe = self.max_bend_per_row() * (c.rows - 1) / np.radians(MAX_BEND_DEGREES)
            raise ValueError(
                f"drape_curvature {c.drape_curvature} bends each row by "
                f"{np.degrees(self.bend_per_row()):.2f} deg, past the "
                f"{np.degrees(self.max_bend_per_row()):.2f} deg that keeps the arms "
                f"clear over {c.rows} rows. Use drape_curvature <= {safe:.2f}, or "
                f"more rows - the same curve spread over more rows bends each one less")

    def validate_capturable(self):
        c = self.config
        if self.head_height_limit() <= c.hole_height:
            raise ValueError(
                f"no head can both lock and clear the stem: hole_height "
                f"{c.hole_height} must be below thickness - 2*stem_height "
                f"({self.head_height_limit():.2f}). Thicken the sheet, lower "
                f"stem_height, or shorten the hole")
        if self.head_height() <= c.hole_height:
            raise ValueError("pin head must be taller than the hole or the joint pulls apart")
        if self.pin_height() <= 0:
            raise ValueError(f"hole_height {c.hole_height} leaves no room for a pin "
                             f"at clearance_gap {c.clearance_gap}")
        if c.hole_width - 2 * c.clearance_gap <= 0:
            raise ValueError(f"hole_width {c.hole_width} leaves no room for a pin "
                             f"at clearance_gap {c.clearance_gap}")
        near, far = self.head_room()
        if far - near <= 0:
            raise ValueError(
                f"no room for a pin head between the core and the loop at "
                f"clearance_gap {c.clearance_gap}: raise loop_fraction above "
                f"{c.loop_fraction} or lower core_fraction below {c.core_fraction}")
        if self.core_radius() > self.max_core_radius():
            raise ValueError(
                f"core reaches {self.core_radius():.2f} mm along the arm axes but only "
                f"{self.max_core_radius():.2f} mm is free. Lower core_fraction below "
                f"{2 * self.max_core_radius() / c.pitch:.3f}, or widen the pitch")
        # Reached only by a config that defeats the head-room check above; kept
        # as a guard because core_points can move the core without touching
        # core_fraction.
        head_bottom = self.mid - self.head_height() / 2
        if head_bottom <= c.stem_height:
            raise ValueError(f"pin head would foul the neighbour's stem: raise "
                             f"hole_height or lower stem_height below {head_bottom:.2f}")
        # The pin has to cross the neighbour's loop on its way in.
        neighbour_loop = c.pitch - self.loop_offset
        if not (self.pin_reach() > neighbour_loop + c.loop_depth / 2):
            raise ValueError("the pin does not reach through the neighbour's loop")

    # -- parts ------------------------------------------------------------

    def _core(self):
        import shapely.geometry
        polygon = shapely.geometry.Polygon(self.core_profile())
        if not polygon.is_valid:
            raise ValueError("core profile is self-intersecting")
        return trimesh.creation.extrude_polygon(polygon, height=self.config.thickness)

    def _loop_arm(self):
        """A ring standing across the arm, carried on a bottom-layer stem."""
        c = self.config
        # Arms start at the centre, not at the core edge, so they stay attached
        # whatever shape the core is. The overlap is absorbed by the union.
        loop_near = self.loop_offset - c.loop_depth / 2
        stem = _box([loop_near, c.arm_width, c.stem_height],
                    [loop_near / 2, 0, c.stem_height / 2])
        outer = _box([c.loop_depth, c.arm_width, c.thickness],
                     [self.loop_offset, 0, self.mid])
        hole = _box([c.loop_depth * 2, c.hole_width, c.hole_height],
                    [self.loop_offset, 0, self.mid])
        loop = trimesh.boolean.difference([outer, hole], engine="manifold")
        return [stem, loop]

    def _pin_arm(self):
        """A bar at mid height with a head on the end, pointing along -x."""
        c = self.config
        pin_w = c.hole_width - 2 * c.clearance_gap
        tip = -self.pin_reach()
        shaft = _box([self.pin_reach(), pin_w, self.pin_height()],
                     [-self.pin_reach() / 2, 0, self.mid])
        head = _box([self.head_length(), pin_w, self.head_height()],
                    [tip + self.head_length() / 2, 0, self.mid])
        return [shaft, head]

    def tile(self):
        c = self.config
        parts = [self._core()]
        for turn in (0, 1):
            angle = turn * np.pi / 2
            rotation = trimesh.transformations.rotation_matrix(angle, [0, 0, 1])
            for piece in self._loop_arm() + self._pin_arm():
                moved = piece.copy()
                moved.apply_transform(rotation)
                parts.append(moved)
        return trimesh.boolean.union(parts, engine="manifold")

    # -- lattice ----------------------------------------------------------

    def row_pitch(self):
        return self.config.pitch

    def column_pitch(self):
        return self.config.pitch

    def _drape(self, row):
        return drape_frame(row, self.config.rows, self.config.drape_curvature,
                           self.row_pitch())

    def tile_center(self, row, col):
        y, z, _ = self._drape(row)
        return np.array([col * self.column_pitch(), y, z])

    def tile_angle(self, row):
        _, _, bend = self._drape(row)
        return bend

    def loop_site(self, row, col, axis="x"):
        """Where a tile's loop sits, and which way the arm points."""
        c = self.config
        center = self.tile_center(row, col)
        offset = np.array([self.loop_offset, 0, 0]) if axis == "x" else np.array([0, self.loop_offset, 0])
        return center + offset

    def link_body(self):
        """A tile of row -1: it threads row 0 exactly as a real neighbour does."""
        tile = self.tile()
        angle = self.tile_angle(-1)
        if angle:
            tile.apply_transform(trimesh.transformations.rotation_matrix(angle, [1, 0, 0]))
        return tile

    def link_sites(self):
        """Row -1 of the same lattice, so a connector tile threads row 0."""
        return [(self.tile_center(-1, col), np.array([0.0, 0.0, 1.0]))
                for col in range(self.config.columns)]

    def anchor_points(self):
        return self._anchor_points

    def validate_assembly(self, tile):
        """Prove the built tile still clears its neighbours.

        The named shapes are all checked in the test suite, but core_points
        accepts anything, so the shape a script wires in gets the same proof
        rather than being trusted. Three booleans on one tile - cheap next to
        placing hundreds of them.
        """
        c = self.config
        for label, offset in (("+x", [c.pitch, 0, 0]), ("+y", [0, c.pitch, 0]),
                              ("diagonal", [c.pitch, c.pitch, 0])):
            other = tile.copy()
            other.apply_translation(offset)
            hit = trimesh.boolean.intersection([tile, other], engine="manifold")
            volume = 0.0 if hit is None or len(hit.vertices) == 0 else hit.volume
            if volume > 1e-9:
                raise ValueError(
                    f"this core profile overlaps its {label} neighbour by "
                    f"{volume:.4f} mm3. Keep the profile inside "
                    f"{self.max_core_radius():.2f} mm on the arm axes; the "
                    f"diagonals have far more room")

    def generate(self):
        self.validate_capturable()
        self.validate_drape()
        c = self.config
        tile = self.tile()
        self.validate_assembly(tile)
        parts = []
        self._anchor_points = []
        for row in range(c.rows):
            angle = self.tile_angle(row)
            for col in range(c.columns):
                placed = tile.copy()
                if angle:
                    placed.apply_transform(
                        trimesh.transformations.rotation_matrix(angle, [1, 0, 0]))
                center = self.tile_center(row, col)
                placed.apply_translation(center)
                parts.append(placed)
                if row == 0:
                    self._anchor_points.append(center)
        return trimesh.util.concatenate(parts)
