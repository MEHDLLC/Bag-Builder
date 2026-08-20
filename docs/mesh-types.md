# Mesh Types

Every fabric link type is the same European 4-in-1 ring lattice. They differ
only in whether scales are hung from the rings.

| Type | `fabric.link_type` | Geometry |
|---|---|---|
| Ring | `ring` | the bare ring lattice |
| Scale | `pyramid` | a scale on every ring |
| Hybrid | `hybrid` | a scale on alternating rows |
| Handle | (`handles.count > 0`) | the same lattice, thicker wire, no drape |

## The lattice

    tilt         = +/- 30 degrees, alternating by row
    column pitch = 2.50 * R          (R = ring centreline radius)
    row pitch    = 0.65 * R
    odd rows offset by half a column pitch

These are not tunable. They are the configuration found by searching for one
where every interior ring is linked to exactly four neighbours *and* no two ring
solids come within the clearance gap. Change one and the fabric either falls
apart or fuses into a slab; `tests/test_interlink.py` re-derives both properties
from generated geometry and will fail.

Rows must alternate their lean because two parallel rings can never link - a
ring in a parallel plane never crosses the other's disk.

## Ring sizing

    ring_outer_diameter = 2 * (R + tube_radius)
    aspect ratio        = (R - tube_radius) / tube_radius,  minimum 4.0

Four wires pass through each hole in 4-in-1, so a fat wire in a small ring
cannot link. Below the minimum the builder raises with the diameter or tube
radius that would work. Clearance scales linearly with ring size.

## Scales

Scales cannot interlink - only rings can - so a sheet of nothing but scales is a
tray of loose parts, and alternating ring rows with scale rows would fall apart
along every scale row. Scales therefore hang from the rings: each is seated
outside its ring's hole, which must stay clear for the four neighbouring wires,
and joined to the wire by a lug so it prints attached.
