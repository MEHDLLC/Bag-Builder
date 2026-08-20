import os
import yaml
from src.pipeline.generate import generate


def test_full_pipeline_tote(tmp_path):
    out = str(tmp_path / "tote_out")
    written = generate("configs/examples/tote_small.yaml", out)
    assert any(f.endswith(".stl") for f in written)


def _write_config(tmp_path, **fabric_and_connector):
    with open("configs/examples/tote_small.yaml") as f:
        cfg = yaml.safe_load(f)
    cfg["fabric"].update(fabric_and_connector.get("fabric", {}))
    cfg["connector"] = fabric_and_connector.get("connector", cfg["connector"])
    cfg["export"] = {"formats": ["stl"], "split_by_part": True}
    cfg["fabric"].update({"rows": 4, "columns": 5})
    cfg["handles"] = {"count": 0}
    path = tmp_path / "bag.yaml"
    with open(path, "w") as f:
        yaml.safe_dump(cfg, f)
    return str(path)


def test_hybrid_fabric_generates_through_the_pipeline(tmp_path):
    cfg = _write_config(tmp_path, fabric={"link_type": "hybrid"})
    written = generate(cfg, str(tmp_path / "out"))
    assert "fabric_front.stl" in written


def test_fused_row_emits_a_connector_part(tmp_path):
    # This part used to be silently missing whenever fused_row was chosen.
    cfg = _write_config(tmp_path, connector={"type": "fused_row"})
    written = generate(cfg, str(tmp_path / "out"))
    assert "connector_front.stl" in written
    assert "connector_back.stl" in written
    assert os.path.getsize(written["connector_front.stl"]) > 0


def test_crossbody_hybrid_example_uses_both_new_features(tmp_path):
    with open("configs/examples/crossbody_hybrid.yaml") as f:
        cfg = yaml.safe_load(f)
    assert cfg["fabric"]["link_type"] == "hybrid"
    assert cfg["connector"]["type"] == "fused_row"
    written = generate("configs/examples/crossbody_hybrid.yaml", str(tmp_path / "out"))
    assert any(f.endswith(".stl") for f in written)
