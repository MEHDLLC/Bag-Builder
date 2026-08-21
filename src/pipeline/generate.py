from pathlib import Path
import json
import sys
import yaml
import trimesh
from ..solids.panel import PanelBuilder, PanelConfig
from ..mesh.ring_mesh import RingMeshBuilder, RingMeshConfig, build_handle_mesh
from ..mesh.hybrid_mesh import HybridMeshBuilder, HybridMeshConfig
from ..mesh.tile_mesh import TileMeshBuilder, TileMeshConfig
from ..connectors.connector_builder import ConnectorBuilder, ConnectorConfig
from .validate import validate_config, validate_mesh_geometry, LINK_TYPES
from . import assembly
import numpy as np


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


def _fit_counts(fabric_cfg, body_cfg, bottom_thickness):
    """Rows and columns that fill the bag wall, when fabric.fit_body is set.

    Ring pitch depends only on the ring, so the counts can be worked out before
    any geometry is built.
    """
    from ..mesh.ring_mesh import COLUMN_PITCH_RATIO, ROW_PITCH_RATIO
    opening_h = max(body_cfg.get("height", 220) - bottom_thickness, 1e-9)
    if fabric_cfg.get("link_type") == "tile":
        pitch = fabric_cfg.get("tile_pitch", 7.0)
        return (max(int(np.floor(opening_h / pitch)), 1),
                max(int(np.floor(body_cfg.get("width", 300) / pitch)), 1))
    od = fabric_cfg.get("ring_outer_diameter", 8.0)
    tr = fabric_cfg.get("ring_tube_radius", 0.5)
    radius = od / 2 - tr
    opening = max(body_cfg.get("height", 220) - bottom_thickness, 1e-9)
    # Round down: a sheet that overshoots hangs off the end of the bag.
    columns = int(np.floor(body_cfg.get("width", 300) / (COLUMN_PITCH_RATIO * radius)))
    rows = int(np.floor(opening / (ROW_PITCH_RATIO * radius)))
    return max(rows, 1), max(columns, 1)


def _build_fabric(fabric_cfg):
    link_type = fabric_cfg.get("link_type", "ring")
    if link_type == "tile":
        cfg = TileMeshConfig(pitch=fabric_cfg.get("tile_pitch", 7.0),
                             thickness=fabric_cfg.get("tile_thickness", 0.0),
                             clearance_gap=fabric_cfg.get("clearance_gap", 0.3),
                             core_shape=fabric_cfg.get("tile_shape", "square"),
                             core_points=tuple(map(tuple, fabric_cfg.get("tile_points", ()))),
                             rows=fabric_cfg.get("rows", 20),
                             columns=fabric_cfg.get("columns", 30),
                             drape_curvature=fabric_cfg.get("drape_curvature", 0.3))
        builder = TileMeshBuilder(cfg)
    elif link_type in ("pyramid", "hybrid"):
        cfg = HybridMeshConfig(outer_diameter=fabric_cfg.get("ring_outer_diameter", 8.0),
                                tube_radius=fabric_cfg.get("ring_tube_radius", 0.5),
                                clearance_gap=fabric_cfg.get("clearance_gap", 0.5),
                                rows=fabric_cfg.get("rows", 20), columns=fabric_cfg.get("columns", 30),
                                drape_curvature=fabric_cfg.get("drape_curvature", 0.3),
                                scale_every_row=link_type == "pyramid")
        builder = HybridMeshBuilder(cfg)
    elif link_type == "ring":
        cfg = RingMeshConfig(outer_diameter=fabric_cfg.get("ring_outer_diameter", 8.0),
                              tube_radius=fabric_cfg.get("ring_tube_radius", 0.5),
                              clearance_gap=fabric_cfg.get("clearance_gap", 0.5),
                              rows=fabric_cfg.get("rows", 20), columns=fabric_cfg.get("columns", 30),
                              drape_curvature=fabric_cfg.get("drape_curvature", 0.3))
        builder = RingMeshBuilder(cfg)
    else:
        raise ValueError(f"Unknown fabric.link_type {link_type!r}; "
                         f"expected one of {', '.join(LINK_TYPES)}")
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
                                     ring_tube_radius=handles_cfg.get("ring_tube_radius", 0.875),
                                     clearance_gap=handles_cfg.get("clearance_gap", 0.6))
        meshes[f"handle_{i+1}"] = mesh
    return meshes


def _build_connectors(connector_cfg, fabric_builder, wall_transforms, body_cfg, bottom_thickness):
    """One connector per fabric wall, joining its bottom row to the bottom panel.

    The link sites are carried into the bag frame with the same transform the
    wall got, so the ring lands where the fabric actually is and the stem spans
    the real distance to the bottom panel edge.
    """
    conn_type = connector_cfg.get("type", "loop_hinge")
    # Stem thickness follows the fabric: a wire radius for ring lattices, a
    # fraction of the sheet for tiles, which have no wire.
    # Ask the builder, not the config: a tile's thickness may be derived, and
    # the config carries the 0 sentinel rather than the real number.
    cfg = fabric_builder.config
    thickness = getattr(fabric_builder, "thickness", None) or getattr(cfg, "thickness", 2.4)
    loop_radius = getattr(cfg, "tube_radius", None) or thickness / 4
    cbuilder = ConnectorBuilder(ConnectorConfig(type=conn_type, loop_tube_radius=loop_radius))
    sites = fabric_builder.link_sites()
    if not sites:
        return {}
    connectors = {}
    for wall, side in (("fabric_front", "front"), ("fabric_back", "back")):
        placed_sites = assembly.transform_sites(sites, wall_transforms[wall])
        edge = assembly.bottom_panel_edge(body_cfg, side, bottom_thickness)
        connectors[f"connector_{side}"] = cbuilder.build(edge, fabric_builder, placed_sites)
    return connectors


def generate(config_path, out_dir):
    raw = load_config(config_path)
    validate_config(raw)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    solids_cfg = raw.get("solids", {})
    body_cfg = raw.get("body", {})
    fabric_cfg = dict(raw.get("fabric", {}))
    if fabric_cfg.get("fit_body"):
        rows, columns = _fit_counts(fabric_cfg, body_cfg,
                                    solids_cfg.get("bottom_panel", {}).get("thickness", 3.0))
        fabric_cfg["rows"], fabric_cfg["columns"] = rows, columns
    fabric_mesh, fabric_builder = _build_fabric(fabric_cfg)
    solids, end_builder, bottom_builder = _build_solids(body_cfg, solids_cfg)
    panel_thickness = solids_cfg.get("end_panels", {}).get("thickness", 3.0)
    bottom_thickness = solids_cfg.get("bottom_panel", {}).get("thickness", 3.0)
    placed, wall_transforms = assembly.place(fabric_mesh, solids, body_cfg,
                                             panel_thickness, bottom_thickness)
    handles = _build_handles(raw.get("handles", {}))
    connectors = _build_connectors(raw.get("connector", {}), fabric_builder,
                                   wall_transforms, body_cfg, bottom_thickness)
    validate_mesh_geometry(fabric_mesh, raw.get("solids", {}).get("end_panels", {}).get("material_wall_min", 1.2))
    written = {}
    export_cfg = raw.get("export", {})
    formats = export_cfg.get("formats", ["stl"])
    split = export_cfg.get("split_by_part", True)
    all_parts = {**placed, **handles, **connectors}
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
    coverage = assembly.wall_coverage(body_cfg, fabric_builder, bottom_thickness)
    if min(coverage["covers"]) < 0.9:
        print(f"warning: fabric covers {coverage['covers'][0]:.0%} of the bag width and "
              f"{coverage['covers'][1]:.0%} of its height. Set fabric.fit_body: true, or "
              f"rows: {coverage['rows_to_fill']} and columns: {coverage['columns_to_fill']}, "
              f"to fill the wall.", file=sys.stderr)
    manifest_path = out / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump({"config": raw, "files": list(written.keys()),
                   "coverage": coverage}, f, indent=2)
    written["manifest.json"] = str(manifest_path)
    return written
