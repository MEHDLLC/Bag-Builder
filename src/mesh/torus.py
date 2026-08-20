import numpy as np
import trimesh


def make_torus(outer_diameter, tube_radius, u_seg=24, v_seg=12):
    center_radius = outer_diameter / 2 - tube_radius
    if center_radius <= 0:
        raise ValueError("outer_diameter must be greater than 2 * tube_radius")
    u = np.linspace(0, 2 * np.pi, u_seg, endpoint=False)
    v = np.linspace(0, 2 * np.pi, v_seg, endpoint=False)
    uu, vv = np.meshgrid(u, v, indexing="ij")
    x = (center_radius + tube_radius * np.cos(vv)) * np.cos(uu)
    y = (center_radius + tube_radius * np.cos(vv)) * np.sin(uu)
    z = tube_radius * np.sin(vv)
    verts = np.stack([x.ravel(), y.ravel(), z.ravel()], axis=1)
    faces = []
    for i in range(u_seg):
        for j in range(v_seg):
            a = i * v_seg + j
            b = ((i + 1) % u_seg) * v_seg + j
            c = ((i + 1) % u_seg) * v_seg + (j + 1) % v_seg
            d = i * v_seg + (j + 1) % v_seg
            faces.append([a, b, c])
            faces.append([a, c, d])
    return trimesh.Trimesh(vertices=verts, faces=np.array(faces), process=True)
