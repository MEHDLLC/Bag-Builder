import os
from src.pipeline.generate import generate


def test_full_pipeline_tote(tmp_path):
    out = str(tmp_path / "tote_out")
    written = generate("configs/examples/tote_small.yaml", out)
    assert any(f.endswith(".stl") for f in written)
