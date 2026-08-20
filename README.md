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

### Known gap: assembly layout

The panels and the fabric are still generated in unrelated coordinate frames -
the panel is centred on the origin, the fabric grows away from it - so while the
connector is genuinely linked to the fabric, the distance its stem spans to the
panel is an artefact of that layout rather than a real dimension. Laying the
parts out in one assembly frame is not done yet.

An unrecognised `fabric.link_type` or `connector.type` is rejected by
`validate_config` before any geometry is built, rather than silently falling back.
