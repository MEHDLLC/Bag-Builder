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
    thickness: float = 0.0        # total sheet thickness; 0 derives the minimum
    pin_thickness: float = 0.6    # how thick the pin itself is
    arm_width: float = 3.0        # loop outer width, across the arm
    hole_width: float = 2.0       # the opening the pin threads
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

    # The z budget has to stack up: stem, clearance, head, clearance, stem. Fix
    # any two of thickness, hole height and clearance and the third is decided,
    # so only the pin and the clearance are given and the rest is derived. The
    # first cut fixed all three and fell apart the moment a config asked for a
    # different clearance.

    @property
    def hole_height(self):
        return self.config.pin_thickness + 2 * self.config.clearance_gap

    # How much taller than the hole the head has to be to actually catch on it.
    LOCK_MARGIN = 0.4

    @property
    def min_thickness(self):
        c = self.config
        return (self.hole_height + 2 * (c.stem_height + c.clearance_gap)
                + self.LOCK_MARGIN)

    @property
    def thickness(self):
        return self.config.thickness or self.min_thickness

    @property
    def mid(self):
        return self.thickness / 2

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
        half = self.hole_height / 2
        return self.mid - half, self.mid + half



    def head_height(self):
        """Taller than the hole, so the pin cannot retract through it.

        Sized midway between the smallest head that still locks (the hole
        height) and the tallest that still clears the neighbour's stem. Tying
        it to clearance_gap instead would couple the lock to the print fit, and
        a loose fit would push the head into the stem.
        """
        c = self.config
        return (self.hole_height + self.head_height_limit()) / 2

    def head_height_limit(self):  # noqa: D401
        """Tallest head that still fits under the top of the sheet.

        The head stands on the tongue and grows upward, so what bounds it is the
        room above the tongue, not the neighbour's stem below.
        """
        return (self.thickness - self.config.clearance_gap
                - (self.mid - self.pin_height() / 2))

    def pin_height(self):
        """The pin's own thickness. The hole is this plus clearance each side."""
        return self.config.pin_thickness

    def vertical_clearance(self):
        """The same gap the config asks for, not half of it.

        The pin sits in the hole with this above and below. Halving it here
        made the joint's tightest dimension half the requested clearance -
        0.15 mm at a config asking for 0.30 - which is the one measurement
        that decides whether the sheet frees itself on the bed.
        """
        return self.config.clearance_gap

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
        if self.head_height_limit() <= self.hole_height:
            raise ValueError(
                f"no head can both lock and clear the stem by {c.clearance_gap} mm at "
                f"thickness {self.thickness:.2f}; at least {self.min_thickness:.2f} "
                f"is needed")
        if self.head_height() <= self.hole_height:
            raise ValueError("pin head must be taller than the hole or the joint pulls apart")
        if c.pin_thickness < 0.4:
            raise ValueError(f"pin_thickness {c.pin_thickness} is too thin to print; "
                             f"use at least 0.4")
        if c.thickness and c.thickness < self.min_thickness:
            raise ValueError(
                f"thickness {c.thickness} cannot hold a {c.pin_thickness} mm pin at "
                f"clearance_gap {c.clearance_gap}: the stem, clearance and head need "
                f"at least {self.min_thickness:.2f}. Leave thickness at 0 to derive it")
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
        return trimesh.creation.extrude_polygon(polygon, height=self.thickness)

    def _loop_arm(self):
        """A ring standing across the arm, carried on a bottom-layer stem."""
        c = self.config
        # Arms start at the centre, not at the core edge, so they stay attached
        # whatever shape the core is. The overlap is absorbed by the union.
        loop_near = self.loop_offset - c.loop_depth / 2
        stem = _box([loop_near, c.arm_width, c.stem_height],
                    [loop_near / 2, 0, c.stem_height / 2])
        outer = _box([c.loop_depth, c.arm_width, self.thickness],
                     [self.loop_offset, 0, self.mid])
        hole = _box([c.loop_depth * 2, c.hole_width, self.hole_height],
                    [self.loop_offset, 0, self.mid])
        loop = trimesh.boolean.difference([outer, hole], engine="manifold")
        return [stem, loop]

    def fin_end(self):
        """How far the full-height part of the pin arm may reach.

        It has to stop clear of the neighbour's loop, which is what it would
        run into. Everything out to here is solid from the bed up; only the
        short tongue past it is unsupported.
        """
        c = self.config
        return c.pitch - self.loop_offset - c.loop_depth / 2 - c.clearance_gap

    def tongue_length(self):
        return self.pin_reach() - self.fin_end()

    def _pin_arm(self):
        """A fin standing on the bed, a short tongue, and a head on the tip.

        The first design ran the whole arm at mid height with a head taller than
        it, which left the head's lower lip starting in mid-air - an island the
        nozzle cannot print. Here the arm is solid from the bed out to the
        neighbour's loop, the tongue cantilevers only the little way needed to
        pass through it, and the head grows *upwards* off the tongue rather than
        hanging below it. Nothing starts in mid-air.
        """
        c = self.config
        pin_w = c.hole_width - 2 * c.clearance_gap
        tip = -self.pin_reach()
        fin = _box([self.fin_end(), pin_w, self.thickness],
                   [-self.fin_end() / 2, 0, self.mid])
        tongue_bottom = self.mid - self.pin_height() / 2
        tongue = _box([self.tongue_length(), pin_w, self.pin_height()],
                      [-(self.fin_end() + self.pin_reach()) / 2, 0, self.mid])
        head = _box([self.head_length(), pin_w, self.head_height()],
                    [tip + self.head_length() / 2, 0,
                     tongue_bottom + self.head_height() / 2])
        return [fin, tongue, head]

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

    def neighbour_overlaps(self, tile, offset):
        """Volume the tile and a neighbour share. Zero means they are apart.

        Distance between points cannot answer this: two boxes can pass through
        each other with every vertex far from every other vertex. Overlap needs
        a boolean; only once that is zero is a distance meaningful.
        """
        other = tile.copy()
        other.apply_translation(offset)
        hit = trimesh.boolean.intersection([tile, other], engine="manifold")
        return 0.0 if hit is None or len(hit.vertices) == 0 else hit.volume

    def neighbour_gap(self, tile, offset, samples=3000):
        """Closest approach between a tile and a neighbour, once they are apart.

        Sampled over the surfaces rather than the vertices: these parts are
        boxes, and the closest approach between two boxes is usually edge to
        face, nowhere near a vertex. Only points in the slab where the two
        bounding boxes come together can be the closest pair, so the rest are
        dropped before the distances are computed - without that the matrix is
        big enough to stall the test suite.
        """
        other = tile.copy()
        other.apply_translation(offset)
        here = np.vstack([tile.vertices, trimesh.sample.sample_surface(tile, samples)[0]])
        there = np.vstack([other.vertices, trimesh.sample.sample_surface(other, samples)[0]])
        margin = max(self.config.clearance_gap * 4, 1.0)
        near_here = np.all((here >= other.bounds[0] - margin)
                           & (here <= other.bounds[1] + margin), axis=1)
        near_there = np.all((there >= tile.bounds[0] - margin)
                            & (there <= tile.bounds[1] + margin), axis=1)
        here = here[near_here] if near_here.any() else here
        there = there[near_there] if near_there.any() else there
        return float(np.linalg.norm(here[:, None, :] - there[None, :, :], axis=2).min())

    def validate_assembly(self, tile):
        """Prove the built tile still clears its neighbours by the asked-for gap.

        Not merely that it does not overlap. A core that swells toward the
        diagonals grows into the corridor where the *axis* neighbour's pin head
        sits, between this tile's core and its loop - so the tightest point in
        the sheet moves with the shape even though the joint itself does not.
        Checking only for overlap let clover and star through at 0.23 and 0.21
        mm against a requested 0.30, which prints fused.
        """
        c = self.config
        for label, offset in (("+x", [c.pitch, 0, 0]), ("+y", [0, c.pitch, 0]),
                              ("diagonal", [c.pitch, c.pitch, 0])):
            volume = self.neighbour_overlaps(tile, offset)
            gap = None if volume > 1e-9 else self.neighbour_gap(tile, offset)
            # The gap is sampled, so compare with a little tolerance rather
            # than rejecting a shape that measures 0.294 against 0.300.
            if gap is not None and gap >= c.clearance_gap * 0.97:
                continue
            fix = self.largest_core_fraction()
            detail = (f"overlaps it by {volume:.4f} mm3" if gap is None
                      else f"comes within {gap:.3f} mm of it")
            raise ValueError(
                f"this core profile {detail} at the {label} neighbour, but "
                f"clearance_gap asks for {c.clearance_gap}. Set core_fraction to "
                f"about {fix:.2f} (which may be larger than it is now - enlarging "
                f"the core pushes the neighbour's head clear of the bulge), widen "
                f"the pitch, or ask for a smaller clearance_gap if your printer "
                f"can hold it")

    def largest_core_fraction(self, low=0.10, high=0.44, step=0.02):
        """The biggest core_fraction this shape can use at this clearance.

        Searched over the whole range rather than downward from the current
        value, because the relationship is not monotonic: enlarging the core
        pushes the neighbour's pin head further out, away from the core's own
        diagonal bulge, so a bigger core can open the gap rather than close it.
        Clover fails at 0.30 and passes at 0.36 for exactly that reason.
        """
        from dataclasses import replace
        best = None
        fraction = low
        while fraction <= high + 1e-9:
            trial = TileMeshBuilder(replace(self.config, core_fraction=round(fraction, 2)))
            try:
                trial.validate_capturable()
                tile = trial.tile()
            except ValueError:
                fraction += step
                continue
            # Suggest with a margin, accept with a tolerance. The gap is
            # sampled, so a value that only just clears here would re-measure
            # marginally under there and the advice would be wrong.
            ok = all(trial.neighbour_overlaps(tile, off) <= 1e-9
                     and trial.neighbour_gap(tile, off) >= self.config.clearance_gap * 1.03
                     for off in ([self.config.pitch, 0, 0], [0, self.config.pitch, 0]))
            if ok:
                best = round(fraction, 2)
            fraction += step
        return best if best is not None else low

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
