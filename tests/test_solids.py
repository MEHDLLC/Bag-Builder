import pytest
from src.solids.panel import PanelBuilder, PanelConfig


@pytest.mark.parametrize("profile", ["rectangular", "rounded_rectangle", "trapezoidal"])
def test_panel_generates_watertight(profile):
    cfg = PanelConfig(shape_profile=profile, width=100, height=80, thickness=3)
    mesh = PanelBuilder(cfg).generate()
    assert mesh.is_watertight
