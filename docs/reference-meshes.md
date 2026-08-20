# Reference Meshes

Measurements taken from four reference STLs, with `tools/analyze_mesh.py` and
follow-up sectioning. Recorded here because the files themselves are 5-75 MB and
do not live in the repo.

Neither reference is chainmail. Both are **flat interlocking tiles**: a tile is
captured by its neighbours through hooks that overlap in plan view and pass at
different heights. There are no rings and nothing threads anything.

## fabric_default (75x75, 100x100, 125x125)

One design at three sizes - the tile is identical in all three, only the count
changes.

| | |
|---|---|
| Tile | 7.00 x 7.00 x 2.20 mm, genus 4 |
| Lattice | checkerboard; 4.25 mm orthogonal pitch, 6.01 mm between diagonal neighbours |
| Neighbours | 4, on the diagonals |
| Sheet | flat - every tile centre at the same height, no drape |
| Lateral clearance | 0.283 mm |
| Mesh density | ~5.0 triangles/mm2 |
| Sizes | 145 / 242 / 392 tiles |

The tile is a four-armed pad. Its cross-section is 27.17 mm2 for the full
height *except* a 0.2 mm band at mid-height (z 1.0 to 1.2) where it narrows to
14.19 mm2 and four 1.10 x 1.10 mm posts appear, detached in section but joined
to the tile above and below.

Those posts are the hooks. Each arm forms a bridge over that 0.2 mm band, and a
neighbour's arm sits in the gap the tile vacates there, capped above and below
so it cannot lift out. Four arms, four captured neighbours, four through-holes -
which is exactly the genus 4 the topology reports.

## triflex-200x200

Same mechanism at three-fold symmetry.

| | |
|---|---|
| Link | 12.83 x 12.09 x 4.00 mm, genus 3 |
| Lattice | triangular; 8.0 mm pitch, neighbours at 120 degrees |
| Neighbours | 3 |
| Sheet | flat |
| Clearance | 0.372 mm to both near neighbours, 0.603 mm to the third |
| Mesh density | ~38.3 triangles/mm2 |
| Size | 448 links over 196 x 199 mm, 1.5 M triangles |

The high triangle count comes from curved surfaces - 161 distinct z levels in a
single link, against 4 in a fabric_default tile. That is what makes the file
74 MB for a 200 mm square.

## How this compares to what we build

| | our ring mesh | fabric_default | triflex |
|---|---|---|---|
| Mechanism | interlinked torus rings | hooked flat tiles | hooked flat links |
| Neighbours | 4 | 4 | 3 |
| Clearance | 0.750 mm | 0.283 mm | 0.372 mm |
| Density | ~28.9 tri/mm2 | ~5.0 | ~38.3 |
| Overhangs | curved, rings lean 30 deg | none, flat plates | curved |
| Drape | supported | flat only | flat only |

Two things worth acting on:

**Our clearance is roughly double what these designs use.** Both printed
successfully at 0.28-0.37 mm. Ours is conservative rather than wrong, but it
means finer fabric is available if we want it.

**Flat tiles are far cheaper to represent.** A fabric_default sheet costs about
a sixth of the triangles per square millimetre that our ring mesh does, because
a tile is flat plates and a ring is a tessellated torus. That is the difference
between a 25 MB bag wall and a 4 MB one.
