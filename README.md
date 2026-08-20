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

### Not yet implemented

Two values are accepted by the CLI and the config schema but are not built yet,
and produce no error when chosen:

| Option | What actually happens |
|---|---|
| `fabric.link_type: hybrid` | falls back to the ring mesh |
| `connector.type: fused_row` | no connector part is emitted at all |
