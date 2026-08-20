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
| **Sweep · option combinations** | all 27 shape × link × connector combinations, one artifact each |

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

All three build the same European 4-in-1 ring lattice, in which every interior
ring is topologically linked to exactly four neighbours and no two ring solids
come closer than the clearance gap. Both properties are verified numerically
against the generated geometry in `tests/test_interlink.py`.

| `fabric.link_type` | Geometry |
|---|---|
| `ring` | the bare 4-in-1 ring lattice |
| `pyramid` | scalemail: a scale on every ring |
| `hybrid` | a scale on alternating rows |

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
