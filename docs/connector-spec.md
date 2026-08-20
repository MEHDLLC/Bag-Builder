# Connector Spec

A connector joins a solid panel to the fabric. It has to do two things, and the
original implementation did neither: be *linked* to the fabric, and be *fused*
to the panel.

## Link ring

Every connector places a ring at each of the fabric's link sites - row -1 of the
fabric's own lattice. A ring there threads rings (0, col-1) and (0, col) exactly
the way a real neighbouring row would, so the connector is held by the same
geometry the fabric is verified against, with no separate calculation to get
wrong.

A stem then runs from the ring's rim - not its centre, so the hole stays clear
for the fabric to swing - out to the panel edge.

| Type | Adds |
|---|---|
| `loop_hinge` | nothing; one link ring plus stem per site |
| `socket_peg` | a peg at each panel edge point |
| `fused_row` | one continuous bar tying every stem together |

`fused_row` unions its parts with `manifold3d` rather than concatenating them:
"fused" is the point of the connector, and concatenation leaves overlapping
shells rather than one bar.

## Known gap

Panels and fabric are generated in unrelated coordinate frames, so the stem
length is an artefact of that layout rather than a real dimension. Assembly
positioning is not implemented.

## Validation

`validate_config` rejects any `connector.type` outside the table before geometry
is built, and `ConnectorBuilder.build` raises on one as a backstop.
