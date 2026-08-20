from src.mesh.ring_mesh import RingMeshConfig, RingMeshBuilder


def test_ring_mesh_generates():
    cfg = RingMeshConfig(rows=4, columns=5)
    builder = RingMeshBuilder(cfg)
    mesh = builder.generate()
    assert len(mesh.vertices) > 0
