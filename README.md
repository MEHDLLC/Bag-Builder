# Parametric 3D-Printed Bag Builder

A parametric CAD/CLI toolkit for generating 3D-printable handbag components:
- **Solid parts** (end panels, bottoms, closures)
- **Chainmail/fabric mesh** (ring or pyramid interlocking meshes)
- **Handles** (thicker chainmail-style mesh)
- **Connectors** (join solid parts to mesh parts)

## Getting Started
```bash
pip install -r requirements.txt
python -m src.cli generate --config configs/examples/tote_small.yaml --out output/
```
