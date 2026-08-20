REQUIRED_TOP_LEVEL = ["body", "fabric"]


def validate_config(raw):
    for key in REQUIRED_TOP_LEVEL:
        if key not in raw:
            raise ValueError(f"Missing required config section: {key}")
    fabric = raw["fabric"]
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
