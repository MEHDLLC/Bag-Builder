"""Numeric checks that a ring lattice is actually chainmail.

Two properties decide whether generated fabric is usable, and neither is
visible from a vertex count:

* every ring is *topologically linked* to its neighbours - otherwise the
  fabric is a tray of loose rings;
* no two ring solids interpenetrate - otherwise they fuse into a rigid slab
  on the print bed.

The original generator failed both at once, so they are checked here rather
than assumed.
"""
import numpy as np


def ring_points(center, normal, radius, segments=400):
    """The ring's centreline as a closed polyline."""
    normal = np.asarray(normal, float)
    normal = normal / np.linalg.norm(normal)
    seed = np.array([1.0, 0.0, 0.0])
    if abs(np.dot(seed, normal)) > 0.9:
        seed = np.array([0.0, 1.0, 0.0])
    u = np.cross(normal, seed)
    u /= np.linalg.norm(u)
    v = np.cross(normal, u)
    t = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    return np.asarray(center, float) + radius * (np.cos(t)[:, None] * u + np.sin(t)[:, None] * v)


def is_linked(center_a, normal_a, center_b, normal_b, radius):
    """True when ring B passes through ring A's hole an odd number of times."""
    normal_a = np.asarray(normal_a, float)
    normal_a = normal_a / np.linalg.norm(normal_a)
    center_a = np.asarray(center_a, float)
    points = ring_points(center_b, normal_b, radius)
    side = (points - center_a) @ normal_a
    crossings = 0
    for i in range(len(points)):
        j = (i + 1) % len(points)
        if side[i] == 0:
            continue
        if (side[i] < 0) != (side[j] < 0):
            w = side[i] / (side[i] - side[j])
            crossing = points[i] + w * (points[j] - points[i])
            if np.linalg.norm(crossing - center_a) < radius:
                crossings += 1
    return crossings % 2 == 1


def surface_gap(center_a, normal_a, center_b, normal_b, radius, tube_radius, segments=200):
    """Closest approach of two ring solids. Negative means they interpenetrate."""
    a = ring_points(center_a, normal_a, radius, segments)
    b = ring_points(center_b, normal_b, radius, segments)
    return float(np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2).min()) - 2 * tube_radius


def lattice_report(builder, rows=None, columns=None):
    """Linked-neighbour count and worst clearance for a built ring lattice."""
    from .ring_mesh import ring_normal

    rows = rows if rows is not None else builder.config.rows
    columns = columns if columns is not None else builder.config.columns
    radius = builder.centerline_radius
    tube_radius = builder.config.tube_radius
    tilt = builder.config.tilt_degrees
    sites = {(r, c): (builder.ring_center(r, c), ring_normal(r, tilt))
             for r in range(rows) for c in range(columns)}
    link_counts = {}
    worst = float("inf")
    for (r, c), (center, normal) in sites.items():
        count = 0
        for (r2, c2), (other, other_normal) in sites.items():
            if (r, c) == (r2, c2) or abs(r - r2) > 2 or abs(c - c2) > 2:
                continue
            if is_linked(center, normal, other, other_normal, radius):
                count += 1
            else:
                worst = min(worst, surface_gap(center, normal, other, other_normal,
                                               radius, tube_radius))
        link_counts[(r, c)] = count
    return link_counts, worst
