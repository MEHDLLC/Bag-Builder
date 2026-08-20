import pytest
from src.pipeline.validate import validate_config

BASE = {"body": {}, "fabric": {}}


def _cfg(**overrides):
    cfg = {"body": {}, "fabric": dict(BASE["fabric"])}
    cfg.update(overrides)
    return cfg


@pytest.mark.parametrize("link_type", ["ring", "pyramid", "hybrid"])
def test_every_documented_link_type_validates(link_type):
    validate_config(_cfg(fabric={"link_type": link_type}))


@pytest.mark.parametrize("conn_type", ["loop_hinge", "socket_peg", "fused_row"])
def test_every_documented_connector_type_validates(conn_type):
    validate_config(_cfg(connector={"type": conn_type}))


def test_unknown_link_type_is_rejected():
    with pytest.raises(ValueError, match="fabric.link_type"):
        validate_config(_cfg(fabric={"link_type": "chainmaille"}))


def test_unknown_connector_type_is_rejected():
    with pytest.raises(ValueError, match="connector.type"):
        validate_config(_cfg(connector={"type": "velcro"}))


def test_missing_connector_section_defaults_to_loop_hinge():
    validate_config(_cfg())
