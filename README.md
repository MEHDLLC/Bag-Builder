# Parametric 3D-Printed Bag Builder

A parametric CAD/CLI toolkit for generating 3D-printable handbag components:
- **Solid parts** (end panels, bottoms, closures)
- **Chainmail/fabric mesh** (ring or pyramid interlocking meshes)
- **Handles** (thicker chainmail-style mesh)
- **Connectors** (join solid parts to mesh parts)

## Getting Started

**Option A — locally.**
```bash
pip install -r requirements.txt
python -m src.cli generate --config configs/examples/tote_small.yaml --out output/
python -m src.cli options   # every value each option accepts
```

**Option B — GitHub Actions, no local install.** Open the repo's **Actions** tab
and pick a workflow — each has its own *Run workflow* form:

| Workflow | What it does |
|---|---|
| **Generate · bag** | one bag: pick a preset, override shape, mesh, connector, handles, formats |
| preset `swatch` | a 50 mm test coupon rather than a bag — print `fabric_front.stl` alone to find the clearance your printer frees at |
| **Sweep · option combinations** | all 36 shape × link × connector combinations, one artifact each |

The form starts from a config in `configs/examples/` and overrides the headline
options on top of it, so every field left on *keep* takes the preset's value.
Actions forms allow ten inputs, so anything not on the form goes in *extra_yaml*
as a YAML fragment, merged last over everything else:

```yaml
solids: {end_panels: {thickness: 3.6}}
export: {split_by_part: false}
```

Every run uploads an artifact with the generated parts, the `manifest.json` and
the exact `bag.yaml` that produced them, and repeats the config and the part
list in the job summary. The same composition is available locally:

```bash
python tools/build_config.py --base configs/examples/tote_small.yaml \
    --set body.shape_profile=trapezoidal --set fabric.rows=8 -o bag.yaml
```

### Fabric link types

| `fabric.link_type` | Geometry |
|---|---|
| `ring` | European 4-in-1 ring lattice |
| `pyramid` | scalemail: a scale on every ring |
| `hybrid` | a scale on alternating rows |
| `tile` | flat interlocking tiles - lighter, and prints without overhangs |

The three ring types build the same 4-in-1 lattice, in which every interior ring
is topologically linked to exactly four neighbours and no two ring solids come
closer than the clearance gap. Both properties are verified numerically against
the generated geometry in `tests/test_interlink.py`.

`tile` is a different mechanism entirely - see below.

Scales cannot interlink with each other, so they hang from the rings rather than
replacing them, each joined to its ring's wire by a lug and kept clear of the
hole that four neighbouring wires pass through.

### Ring sizing

The lattice constants (30 degree lean, column pitch 2.5R, row pitch 0.65R) are
not free parameters - they are the configuration that satisfies both properties
above. What you do choose is the ring itself:

    ring_outer_diameter = 2 * (R + tube_radius)
    aspect ratio        = (R - tube_radius) / tube_radius     # must be >= 4

Four wires pass through every hole in 4-in-1, so a fat wire in a small ring
cannot link at all. A ring below the minimum aspect ratio is rejected with a
message telling you what to change; it is not silently built. Clearance scales
with ring size, so a bigger `ring_outer_diameter` at the same aspect ratio gives
both a thicker wire and more room between rings.

### Flat tiles

Modelled on the reference sheets measured in `docs/reference-meshes.md`. A tile
is a flat plate with four arms: two *loops* standing across the arm, and two
*pins* that thread the neighbouring tile's loop. One shape tiles the whole
sheet, because a tile's +x loop is always met by its +x neighbour's -x pin.

Each pin ends in a head taller than the hole it passes through, so the joint
cannot be pulled apart. That only works because the sheet is printed in place
and the head never has to pass through the hole.

Why prefer it: on a full 300 x 220 bag wall it is **9.7 MB against 23.0 MB**
for the ring lattice at equivalent coverage - 3.0 triangles per square
millimetre against 6.8 - and every surface is a flat plate, so nothing
overhangs and nothing needs support.

    fabric: {link_type: tile, tile_pitch: 8.0, fit_body: true}

**It does not yet print without supports.** `tools/check_supports.py` slices a
part and counts *islands* - regions appearing with nothing at all beneath them.
The reference sheets have **zero**; a tile of ours has **two**, because the pin
head is taller than the shaft it rides on, so its lower lip starts in mid-air.
The references avoid this by running their arms full height with a notch in the
middle, so material grows continuously from the bed. Redesigning the arm that
way is the outstanding work; `test_the_tile_still_has_unsupported_islands` pins
the defect until it is done.

The arm geometry, the hole height and the sheet thickness are all derived from
`tile_pitch`, `pin_thickness` and `clearance_gap` rather than given in
millimetres. The z budget has to stack up - stem, clearance, head, clearance,
stem - so fixing all of them independently breaks the joint the moment one
changes. Impossible combinations are rejected with the dimension to change.

`clearance_gap` means the tightest gap **anywhere** in the sheet, which is the
number that decides whether it frees itself on the bed. It used to be halved
vertically, and the pin head sat 0.10 mm off the neighbour's stem whatever was
asked for, so a config asking for 0.30 mm really delivered 0.15 mm.

#### The tile's shape is a variable; the joint is not

The joint - loop, pin and head - is fixed and verified. The **core** those arms
hang off is free, because the constraint on it is lopsided: along the four arm
axes only about 1.3 mm is spare at a 7 mm pitch, but a diagonal neighbour's
centre is 9.9 mm away. A profile that swells into the diagonals has room a
square core never uses.

```yaml
fabric: {link_type: tile, tile_shape: clover}
```

| `fabric.tile_shape` | |
|---|---|
| `square` `diamond` `circle` | the plain ones |
| `hexagon` `octagon` | flatter faces |
| `clover` `star` | swell into the diagonals: denser fabric, less see-through |

Every profile is normalised so its radius **on the arm axes** is exactly the
core radius, then only the roomy diagonals differ. That is what makes swapping
shapes safe: the binding direction never moves, so the joint is untouched -
all seven shapes thread their neighbour with an identical 0.504 mm3 of
material in the hole.

Shape changes how much of the sheet is solid: on the same lattice, `diamond`
gives 26.5 mm3 per tile and `star` 39.0 mm3, a 47% range in density with the
same mechanics.

For a shape that is not in the list, a script can wire in any radius-by-angle
formula through `tile_points`:

```python
theta = np.linspace(0, 2 * np.pi, 96, endpoint=False)
r = limit * 0.8 * (1 + 0.35 * np.sin(8 * theta) ** 2)      # any formula
points = np.column_stack([r * np.cos(theta), r * np.sin(theta)])
```

Anything supplied that way is checked against its neighbours with a boolean
before the sheet is built, and rejected with the overlap volume if it fouls -
so a bad formula fails loudly instead of printing as a fused slab. Keep the
profile four-fold symmetric: a three- or six-lobed one puts a lobe on an arm
axis, and that is exactly where there is no room.

One limit that rings do not have: a tile's arms reach past the pitch into its
neighbour, so relative rotation between rows closes the clearance at the arm tip.
Drape is checked against that and rejected when too much curve is asked of too
few rows - the fix is more rows, not less curve, since the same curve spread
over more rows bends each one less. A full bag wall has plenty.

### Connector types

| `connector.type` | Geometry |
|---|---|
| `loop_hinge` | a link ring per site, each with a stem to the panel |
| `socket_peg` | the same, plus a peg at each panel edge point |
| `fused_row` | the same, tied together by one continuous bar |

Every connector's link ring is a ring of the fabric's own lattice placed one row
before the first, so it threads row 0 exactly the way a real neighbouring row
would and is held by the same verified geometry.

### Assembly

Parts are placed into one bag frame - x is width, y is depth, z is height with
z=0 the underside of the bottom panel:

| Part | Placement |
|---|---|
| `bottom_panel` | flat at z=0 |
| `end_panel_left` / `end_panel_right` | stood on end at x = -W/2 and +W/2 |
| `fabric_front` / `fabric_back` | tipped up into walls at y = -D/2 and +D/2 |
| `connector_front` / `connector_back` | joining each wall's bottom row to the bottom panel |

Which edge carries the connector is decided by the lattice rather than by
preference: in 4-in-1 links only run between adjacent *rows*, so a sheet can be
joined along a horizontal row. A vertical column edge has no lattice position
that links it, which is why the fabric hangs from its bottom row instead of
being seamed up the sides.

### Sizing the fabric to the bag

Rows and columns are counts, not dimensions, so a fabric can be far smaller than
the wall it is supposed to cover - which is what makes a generated bag come out
as a flat mat. Every run reports coverage in `manifest.json` and warns when the
fabric leaves more than a tenth of the wall bare:

    warning: fabric covers 88% of the bag width and 21% of its height.
    Set fabric.fit_body: true, or rows: 95 and columns: 34, to fill the wall.

`fabric.fit_body: true` derives the counts from the body dimensions, rounding
down so the sheet never hangs off the end. Ring size drives the count: filling a
300x220 bag needs about 3300 rings per wall at an 8mm ring but about 860 at a
16mm one, so scale the ring to the bag rather than the other way round.

An unrecognised `fabric.link_type` or `connector.type` is rejected by
`validate_config` before any geometry is built, rather than silently falling back.
