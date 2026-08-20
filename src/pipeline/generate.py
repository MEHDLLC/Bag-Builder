from pathlib import Path
import json
import yaml
import trimesh
from ..solids.panel import PanelBuilder, PanelConfig
from ..mesh.ring_mesh import RingMeshBuilder, RingMeshConfig, build_handle_mesh
from ..mesh.pyramid_mesh import PyramidMeshBuilder, PyramidMeshConfig
from ..connectors.connector_builder import ConnectorBuilder, ConnectorConfig
from .validate import validate_config, validate_mesh_geometry


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


def _build_fabric(fabric_cfg):
    link_type = fabric_cfg.get("link_type", "ring")
    if link_type == "pyramid":
        cfg = PyramidMeshConfig(base_size=fabric_cfg.get("ring_outer_diameter", 8.0),
                                 height=fabric_cfg.get("ring_tube_radius", 1.0) * 3,
                                 clearance_gap=fabric_cfg.get("clearance_gap", 0.4),
                                 rows=fabric_cfg.get("rows", 20), columns=fabric_cfg.get("columns", 30))
        builder = PyramidMeshBuilder(cfg)
    else:
        cfg = RingMeshConfig(outer_diameter=fabric_cfg.get("ring_outer_diameter", 8.0),
                              tube_radius=fabric_cfg.get("ring_tube_radius", 1.0),
                              clearance_gap=fabric_cfg.get("clearance_gap", 0.5),
                              rows=fabric_cfg.get("rows", 20), columns=fabric_cfg.get("columns", 30),
                              drape_curvature=fabric_cfg.get("drape_curvature", 0.3))
        builder = RingMeshBuilder(cfg)
    return builder.generate(), builder


def _build_solids(body_cfg, solids_cfg):
    end_cfg = solids_cfg.get("end_panels", {})
    bottom_cfg = solids_cfg.get("bottom_panel", {})
    end_panel_cfg = PanelConfig(shape_profile=body_cfg.get("shape_profile", "rounded_rectangle"),
                                 width=body_cfg.get("depth", 90), height=body_cfg.get("height", 220),
                                 thickness=end_cfg.get("thickness", 3.0), corner_radius=body_cfg.get("corner_radius", 15.0))
    bottom_panel_cfg = PanelConfig(shape_profile="rectangular", width=body_cfg.get("width", 300),
                                    height=body_cfg.get("depth", 90), thickness=bottom_cfg.get("thickness", 3.0), corner_radius=0)
    end_builder = PanelBuilder(end_panel_cfg)
    bottom_builder = PanelBuilder(bottom_panel_cfg)
    return {"end_panel_left": end_builder.generate(), "end_panel_right": end_builder.generate(),
            "bottom_panel": bottom_builder.generate()}, end_builder, bottom_builder


def _build_handles(handles_cfg):
    if not handles_cfg or handles_cfg.get("count", 0) == 0:
        return {}
    count = handles_cfg.get("count", 2)
    meshes = {}
    for i in range(count):
        mesh, _ = build_handle_mesh(length_mm=handles_cfg.get("length", 350), width_rows=handles_cfg.get("width_rows", 3),
                                     ring_outer_diameter=handles_cfg.get("ring_outer_diameter", 14.0),
                                     ring_tube_radius=handles_cfg.get("ring_tube_radius", 2.2),
                                     clearance_gap=handles_cfg.get("clearance_gap", 0.6))
        meshes[f"handle_{i+1}"] = mesh
    return meshes


def _build_connectors(connector_cfg, end_builder, fabric_builder):
    conn_type = connector_cfg.get("type", "loop_hinge")
    cfgattr = getattr(fabric_builder, "config", None)
    loop_radius = getattr(cfgattr, "tube_radius", 1.0) * 1.2 if cfgattr else 1.2
    cbuilder = ConnectorBuilder(ConnectorConfig(type=conn_type, loop_tube_radius=loop_radius))
    edge = end_builder.edge_curve("top")
    anchors = fabric_builder.anchor_points()
    if len(anchors) == 0:
        return {}
    return {"connector_left": cbuilder.build(edge, anchors)}


def generate(config_path, out_dir):
    raw = load_config(config_path)
    validate_config(raw)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    fabric_mesh, fabric_builder = _build_fabric(raw.get("fabric", {}))
    solids, end_builder, bottom_builder = _build_solids(raw.get("body", {}), raw.get("solids", {}))
    handles = _build_handles(raw.get("handles", {}))
    connectors = _build_connectors(raw.get("connector", {}), end_builder, fabric_builder)
    validate_mesh_geometry(fabric_mesh, raw.get("solids", {}).get("end_panels", {}).get("material_wall_min", 1.2))
    written = {}
    export_cfg = raw.get("export", {})
    formats = export_cfg.get("formats", ["stl"])
    split = export_cfg.get("split_by_part", True)
    all_parts = {"fabric": fabric_mesh, **solids, **handles, **connectors}
    if split:
        for name, mesh in all_parts.items():
            if mesh is None or len(mesh.vertices) == 0:
                continue
            for fmt in formats:
                fp = out / f"{name}.{fmt}"
                mesh.export(fp)
                written[f"{name}.{fmt}"] = str(fp)
    else:
        combined = trimesh.util.concatenate([m for m in all_parts.values() if m is not None and len(m.vertices) > 0])
        for fmt in formats:
            fp = out / f"assembly.{fmt}"
            combined.export(fp)
            written[f"assembly.{fmt}"] = str(fp)
    manifest_path = out / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump({"config": raw, "files": list(written.keys())}, f, indent=2)
    written["manifest.json"] = str(manifest_path)
    return written
