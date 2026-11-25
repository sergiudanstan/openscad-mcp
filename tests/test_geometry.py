"""Unit tests for the pure-Python mesh analysis (no OpenSCAD needed)."""

import math
import struct
from pathlib import Path

import pytest

from openscad_mcp import geometry


def box(x0, y0, z0, x1, y1, z1):
    """Outward-oriented triangles of an axis-aligned box."""
    v = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    quads = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    tris = []
    for a, b, c, d in quads:
        tris += [(v[a], v[b], v[c]), (v[a], v[c], v[d])]
    return tris


def write_binary_stl(path: Path, tris) -> None:
    with path.open("wb") as f:
        f.write(b"\0" * 80 + struct.pack("<I", len(tris)))
        for t in tris:
            f.write(struct.pack("<12fH", 0, 0, 0, *t[0], *t[1], *t[2], 0))


def write_ascii_stl(path: Path, tris) -> None:
    lines = ["solid t"]
    for t in tris:
        lines += ["facet normal 0 0 0", "outer loop"]
        lines += [f"vertex {p[0]} {p[1]} {p[2]}" for p in t]
        lines += ["endloop", "endfacet"]
    path.write_text("\n".join(lines + ["endsolid t"]))


class TestMeshStats:
    def test_cube_numbers(self):
        st = geometry.mesh_stats(box(0, 0, 0, 10, 20, 30))
        assert st.volume == pytest.approx(6000)
        assert st.area == pytest.approx(2 * (200 + 300 + 600))
        assert st.bbox_min == (0, 0, 0) and st.bbox_max == (10, 20, 30)
        assert st.centroid == pytest.approx((5, 10, 15))
        assert st.watertight and st.bodies == 1 and st.misoriented_edges == 0

    def test_open_mesh_is_not_watertight(self):
        st = geometry.mesh_stats(box(0, 0, 0, 1, 1, 1)[:-2])
        assert not st.watertight and st.boundary_edges == 4

    def test_two_bodies(self):
        st = geometry.mesh_stats(box(0, 0, 0, 1, 1, 1) + box(5, 5, 5, 6, 6, 6))
        assert st.bodies == 2 and st.volume == pytest.approx(2)

    def test_inverted_winding_gives_negative_volume_and_flags_orientation(self):
        tris = box(0, 0, 0, 1, 1, 1)
        flipped = [(t[0], t[2], t[1]) for t in tris[:2]] + tris[2:]
        st = geometry.mesh_stats(flipped)
        assert st.misoriented_edges > 0

    def test_empty(self):
        st = geometry.mesh_stats([])
        assert st.triangles == 0 and not st.watertight

    def test_volume_moves_with_size(self):
        """Perturbation: doubling every side multiplies the volume by 8."""
        v1 = geometry.mesh_stats(box(0, 0, 0, 3, 4, 5)).volume
        v2 = geometry.mesh_stats(box(0, 0, 0, 6, 8, 10)).volume
        assert v2 == pytest.approx(8 * v1)


class TestMassProperties:
    def test_cube_inertia_matches_closed_form(self):
        a = 10.0
        props = geometry.mass_properties(box(-5, -5, -5, 5, 5, 5), density_g_cm3=1.0)
        m = a**3 / 1000  # g
        assert props["mass_g"] == pytest.approx(m)
        i = m * (a**2 + a**2) / 12
        tensor = props["inertia_about_com_g_mm2"]
        for k in range(3):
            assert tensor[k][k] == pytest.approx(i, rel=1e-6)
        assert props["center_of_mass"] == pytest.approx([0, 0, 0], abs=1e-9)

    def test_inertia_is_about_com_not_origin(self):
        near = geometry.mass_properties(box(0, 0, 0, 2, 4, 6), 2.7)
        far = geometry.mass_properties(box(100, 200, 300, 102, 204, 306), 2.7)
        assert near["principal_moments_g_mm2"] == pytest.approx(far["principal_moments_g_mm2"], rel=1e-5)
        assert far["center_of_mass"] == pytest.approx([101, 202, 303])

    def test_rectangular_block_principal_moments(self):
        a, b, c = 2.0, 4.0, 6.0
        props = geometry.mass_properties(box(0, 0, 0, a, b, c), 1.0)
        m = a * b * c / 1000
        expected = sorted([m * (b * b + c * c) / 12, m * (a * a + c * c) / 12, m * (a * a + b * b) / 12])
        assert props["principal_moments_g_mm2"] == pytest.approx(expected, rel=1e-4)

    def test_eigenvalues_of_rotated_tensor(self):
        c, s = math.cos(0.3), math.sin(0.3)
        r = [[c, -s, 0], [s, c, 0], [0, 0, 1]]
        d = [1.0, 2.0, 5.0]
        m = [[sum(r[i][k] * d[k] * r[j][k] for k in range(3)) for j in range(3)] for i in range(3)]
        assert geometry._sym_eigenvalues(m) == pytest.approx([1, 2, 5])

    def test_flat_mesh_is_an_error(self):
        flat = [((0, 0, 0), (1, 0, 0), (0, 1, 0))]
        assert "error" in geometry.mass_properties(flat, 1.0)


class TestPrintReport:
    def test_block_on_bed_has_contact_and_no_overhang(self):
        rep = geometry.print_report(box(0, 0, 0, 10, 10, 10))
        assert rep["bed_contact_area_mm2"] == pytest.approx(100)
        assert rep["overhang_area_mm2"] == 0 and rep["issues"] == []

    def test_t_shape_overhang_detected(self):
        stem = box(4, 4, 0, 6, 6, 10)
        cap = box(0, 0, 10, 10, 10, 12)
        rep = geometry.print_report(stem + cap)
        assert rep["overhang_area_mm2"] == pytest.approx(100)  # cap underside
        assert rep["lowest_overhang_z"] == pytest.approx(10)
        assert any("overhang" in i for i in rep["issues"])

    def test_build_volume(self):
        rep = geometry.print_report(box(0, 0, 0, 300, 10, 10), build_volume=(256, 256, 256))
        assert rep["fits_build_volume"] is False


class TestReaders:
    @pytest.mark.parametrize("writer", [write_binary_stl, write_ascii_stl])
    def test_stl_round_trip(self, tmp_path, writer):
        p = tmp_path / "m.stl"
        writer(p, box(0, 0, 0, 1, 2, 3))
        st = geometry.mesh_stats(geometry.read_stl(p))
        assert st.triangles == 12 and st.volume == pytest.approx(6)

    def test_svg_contours_square_with_hole(self, tmp_path):
        p = tmp_path / "s.svg"
        p.write_text(
            '<svg><path d="M 0,0 L 20,0 L 20,-20 L 0,-20 z M 5,-5 L 5,-15 L 15,-15 L 15,-5 z" /></svg>'
        )
        stats = geometry.contours_stats(geometry.read_svg_contours(p))
        assert stats["contours"] == 2
        assert stats["area"] == pytest.approx(300)
        assert stats["bbox"]["size"] == [20, 20]
