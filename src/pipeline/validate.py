REQUIRED_TOP_LEVEL = ["body", "fabric"]
LINK_TYPES = ("ring", "pyramid", "hybrid", "tile")
CONNECTOR_TYPES = ("loop_hinge", "socket_peg", "fused_row")


def validate_config(raw):
    for key in REQUIRED_TOP_LEVEL:
        if key not in raw:
            raise ValueError(f"Missing required config section: {key}")
    fabric = raw["fabric"]
    link_type = fabric.get("link_type", "ring")
    if link_type not in LINK_TYPES:
        raise ValueError(f"fabric.link_type must be one of {', '.join(LINK_TYPES)}; got {link_type!r}")
    conn_type = (raw.get("connector") or {}).get("type", "loop_hinge")
    if conn_type not in CONNECTOR_TYPES:
        raise ValueError(f"connector.type must be one of {', '.join(CONNECTOR_TYPES)}; got {conn_type!r}")
    od = fabric.get("ring_outer_diameter", 8.0)
    tr = fabric.get("ring_tube_radius", 1.0)
    gap = fabric.get("clearance_gap", 0.5)
    if od <= 2 * tr + gap:
        raise ValueError("fabric.ring_outer_diameter must be greater than 2*ring_tube_radius+clearance_gap")
    handles = raw.get("handles")
    if handles and handles.get("count", 0) > 0:
        h_od = handles.get("ring_outer_diameter", 14.0)
        h_tr = handles.get("ring_tube_radius", 2.2)
        h_gap = handles.get("clearance_gap", 0.6)
        if h_od <= 2 * h_tr + h_gap:
            raise ValueError("handles ring_outer_diameter must be greater than 2*ring_tube_radius+clearance_gap")


def validate_mesh_geometry(mesh, wall_min=1.2):
    if mesh is None or len(mesh.vertices) == 0:
        return
    if mesh.is_empty:
        raise ValueError("Generated fabric mesh is empty")
