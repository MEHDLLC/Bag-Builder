# ARCHITECTURE

Three geometry domains share one connector interface:
1. Solid Parts Module
2. Mesh/Fabric Module (ring/pyramid/hybrid)
3. Handle Module (thicker reinforced ring mesh)

Connector types: loop_hinge, socket_peg, fused_row. All three are
implemented; see docs/connector-spec.md. loop_hinge and socket_peg emit one
body per anchor, fused_row unions the run into a single bar.

Fabric link types ring, pyramid and hybrid are all implemented; hybrid
alternates ring rows with pyramid scale rows on the ring lattice. See
docs/mesh-types.md.

Unrecognised values for either are rejected by validate_config before any
geometry is built.
