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

## Placement

Link sites are carried into the bag frame with the same transform their fabric
wall received, so the ring lands where the fabric actually is. Each site is then
joined to the *nearest* point on the panel edge. Spreading sites evenly along
the whole edge instead ties a ring in the middle of the fabric to a point at the
far end of the panel whenever the fabric is narrower than the bag, which is what
produced 130mm stems before.

One connector is emitted per fabric wall: `connector_front` and
`connector_back`.

## Validation

`validate_config` rejects any `connector.type` outside the table before geometry
is built, and `ConnectorBuilder.build` raises on one as a backstop.
