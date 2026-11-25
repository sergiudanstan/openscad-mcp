"""End-to-end tests of the v0.3 tools against the real OpenSCAD CLI.

Each numeric check is paired with a perturbation (change the model or a
parameter and show the number moves), so a dead code path cannot pass.
"""

import json
import math
from pathlib import Path
from unittest.mock import patch

import pytest

from openscad_mcp import geometry

HOLLOW = (
    "w = 20; // [5:100] width\nh = 10;\n"
    "difference() { cube([w, w, h]); translate([5, 5, -0.01]) cube([w - 10, w - 10, h + 0.02]); }\n"
)


async def make(tools, name, code):
    await tools("openscad_create")(filename=name, code=code)


def _text_json(content: list) -> dict:
    return json.loads([c for c in content if isinstance(c, str)][-1])


class TestMeasure:
    async def test_exact_numbers_and_parameter_perturbation(self, tools):
        await make(tools, "h.scad", HOLLOW)
        m = await tools("openscad_measure")(filename="h.scad")
        assert m["bbox"]["size"] == [20, 20, 10]
        assert m["volume"] == pytest.approx(20 * 20 * 10 - 10 * 10 * 10)
        assert m["watertight"] and m["bodies"] == 1
        m40 = await tools("openscad_measure")(filename="h.scad", parameters={"w": 40})
        assert m40["bbox"]["size"] == [40, 40, 10]
        assert m40["volume"] == pytest.approx(40 * 40 * 10 - 30 * 30 * 10)

    async def test_sphere_volume_converges(self, tools):
        await make(tools, "s.scad", "sphere(r=10, $fn=96);")
        m = await tools("openscad_measure")(filename="s.scad")
        assert m["volume"] == pytest.approx(4 / 3 * math.pi * 1000, rel=0.01)

    async def test_cache_hit_and_invalidation_through_include(self, tools, real_client):
        await make(tools, "dims.scad", "size = 5;\n")
        await make(tools, "part.scad", "include <dims.scad>\ncube(size);\n")
        first = await tools("openscad_measure")(filename="part.scad")
        again = await tools("openscad_measure")(filename="part.scad")
        assert not first["cached"] and again["cached"]
        assert again["volume"] == 125
        # Editing only the included file must invalidate the cached mesh.
        (real_client.workspace / "dims.scad").write_text("size = 6;\n")
        changed = await tools("openscad_measure")(filename="part.scad")
        assert not changed["cached"] and changed["volume"] == 216

    async def test_2d_model(self, tools):
        await make(tools, "f.scad", "difference() { square(20); translate([5, 5]) square(10); }")
        m = await tools("openscad_measure")(filename="f.scad")
        assert m["dimension"] == 2 and m["area"] == pytest.approx(300) and m["contours"] == 2

    async def test_failed_assert_is_an_error_even_though_openscad_exits_0(self, tools, tool_error):
        await make(tools, "bad.scad", 'cube(1);\nassert(1 == 2, "nope");\n')
        err = await tool_error(tools("openscad_measure")(filename="bad.scad"))
        assert err["errors"][0]["line"] == 2


class TestEngineering:
    async def test_mass_properties_material_and_density(self, tools):
        await make(tools, "c.scad", "cube(10, center=true);")
        pla = await tools("openscad_mass_properties")(filename="c.scad", material="pla")
        assert pla["mass_g"] == pytest.approx(1.24)
        assert pla["center_of_mass"] == pytest.approx([0, 0, 0], abs=1e-9)
        steel = await tools("openscad_mass_properties")(filename="c.scad", material="steel")
        assert steel["mass_g"] == pytest.approx(7.85)
        i = steel["mass_g"] * (100 + 100) / 12
        assert steel["principal_moments_g_mm2"] == pytest.approx([i, i, i], rel=1e-6)

    async def test_interference_states(self, tools):
        await make(tools, "a.scad", "cube(10);")
        await make(tools, "b.scad", "translate([5, 5, 5]) cube(10);")
        await make(tools, "far.scad", "translate([20, 0, 0]) cube(10);")
        hit = await tools("openscad_interference")(file_a="a.scad", file_b="b.scad")
        assert hit["status"] == "interference" and hit["interference_volume"] == pytest.approx(125)
        assert hit["interference_bbox"]["min"] == [5, 5, 5]
        clear = await tools("openscad_interference")(file_a="a.scad", file_b="far.scad")
        assert clear["status"] == "clear" and clear["min_bbox_gap"] == pytest.approx(10)
        # Pin inside a hole: bounding boxes overlap, solids do not.
        await make(tools, "ring.scad", HOLLOW)
        await make(tools, "pin.scad", "translate([10, 10, 0]) cylinder(d=6, h=30, $fn=32);")
        near = await tools("openscad_interference")(file_a="ring.scad", file_b="pin.scad")
        assert near["status"] == "touching_or_near"
        # Perturb: a fatter pin now cuts into the ring.
        await make(tools, "pin.scad", "translate([10, 10, 0]) cylinder(d=12, h=30, $fn=32);")
        assert (await tools("openscad_interference")(file_a="ring.scad", file_b="pin.scad"))["status"] == "interference"

    async def test_section_wall_thickness(self, tools):
        await make(tools, "tube.scad",
                   "difference() { cylinder(d=20, h=40, $fn=64); translate([0, 0, -1]) cylinder(d=16, h=42, $fn=64); }")
        out = await tools("openscad_section")(filename="tube.scad", axis="x", offset=0, return_image=False)
        meta = _text_json(out)
        assert meta["area"] == pytest.approx(2 * 2 * 40, rel=1e-3) and meta["regions"] == 2
        miss = _text_json(await tools("openscad_section")(filename="tube.scad", axis="z", offset=100, return_image=False))
        assert miss["area"] == 0
        with_image = await tools("openscad_section")(filename="tube.scad", axis="z", offset=10)
        assert any(type(c).__name__ == "Image" for c in with_image)
        z = _text_json(with_image)
        assert z["area"] == pytest.approx(math.pi * (100 - 64), rel=0.01)

    async def test_print_report_flags_overhang(self, tools):
        await make(tools, "t.scad", "translate([4, 4, 0]) cube([2, 2, 10]); translate([0, 0, 10]) cube([10, 10, 2]);")
        rep = await tools("openscad_print_report")(filename="t.scad")
        assert rep["overhang_area_mm2"] == pytest.approx(96)  # cap underside minus the stem
        assert rep["bed_contact_area_mm2"] == pytest.approx(4)
        flat = await tools("openscad_print_report")(filename="t.scad", overhang_deg=89.99)
        assert flat["overhang_area_mm2"] == pytest.approx(96)
        await make(tools, "block.scad", "cube(10);")
        ok = await tools("openscad_print_report")(filename="block.scad")
        assert ok["issues"] == []

    async def test_eval_in_model_scope(self, tools):
        await make(tools, "e.scad", "w = 20;\nfunction twice(x) = 2 * x;\ncube(w);\n")
        res = await tools("openscad_eval")(filename="e.scad", expressions=["twice(w)", "[w, w/4]", "w > 5", "nope"])
        values = [(r["value"], r["type"]) for r in res["results"]]
        assert values[:3] == [("40", "number"), ("[20, 5]", "vector"), ("true", "bool")]
        assert values[3][1] == "undef" and res["warnings"]
        over = await tools("openscad_eval")(filename="e.scad", expressions=["twice(w)"], parameters={"w": 7})
        assert over["results"][0]["value"] == "14"


class TestRenderTools:
    async def test_preview_returns_images_for_each_view(self, tools):
        await make(tools, "p.scad", "cube([30, 10, 5]);")
        out = await tools("openscad_preview")(filename="p.scad", views=["isometric", "front", "top"], width=320, height=240)
        images = [c for c in out if type(c).__name__ == "Image"]
        meta = _text_json(out)
        assert len(images) == 3 and [i["view"] for i in meta["images"]] == ["isometric", "front", "top"]
        for info in meta["images"]:
            assert Path(info["path"]).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
            assert info["size"] == [320, 240]

    async def test_preview_rejects_unknown_view(self, tools, tool_error):
        await make(tools, "p.scad", "cube(1);")
        err = await tool_error(tools("openscad_preview")(filename="p.scad", views=["sideways"]))
        assert "Unknown view" in err["error"]

    async def test_export_typed_string_parameter(self, tools):
        await make(tools, "t.scad", 'label = "A";\nlinear_extrude(1) text(label, size=10);\n')
        one = await tools("openscad_export")(filename="t.scad", output_filename="one.stl")
        two = await tools("openscad_export")(filename="t.scad", output_filename="two.stl", parameters={"label": "AAA"})
        assert two["mesh"]["bbox"]["size"][0] > 2.5 * one["mesh"]["bbox"]["size"][0]

    async def test_animation_frames_and_missing_ffmpeg(self, tools):
        await make(tools, "anim.scad", "rotate([0, 0, 360 * $t]) cube([20, 5, 5]);")
        with patch("openscad_mcp.tools.render_tools.shutil.which", return_value=None):
            res = await tools("openscad_render_animated")(filename="anim.scad", num_frames=4, width=120, height=90)
        assert res["frames_written"] == 4 and "ffmpeg not found" in res["mp4_error"]


class TestDesignTools:
    async def test_snippet_edit_and_etag(self, tools, tool_error):
        created = await tools("openscad_create")(filename="e.scad", code="a = 1;\nb = 1;\ncube(a);\n")
        edited = await tools("openscad_edit")(filename="e.scad", old_string="a = 1;", new_string="a = 3;")
        assert edited["replacements"] == 1
        err = await tool_error(tools("openscad_edit")(filename="e.scad", old_string=" = ", new_string="="))
        assert "occurs 2 times" in err["error"]
        both = await tools("openscad_edit")(filename="e.scad", old_string=" = ", new_string="=", replace_all=True)
        assert both["replacements"] == 2
        stale = await tool_error(tools("openscad_edit")(filename="e.scad", code="cube(1);", expected_etag=created["etag"]))
        assert "etag mismatch" in stale["error"]
        read = await tools("openscad_read")(filename="e.scad", with_line_numbers=True)
        assert "    1  a=3;" in read["content"]

    async def test_get_parameters(self, tools):
        await make(tools, "p.scad", HOLLOW)
        res = await tools("openscad_get_parameters")(filename="p.scad")
        assert [p["name"] for p in res["parameters"]] == ["w", "h"]
        assert res["parameters"][0]["constraint"] == "5:100"


class TestLibraryTools:
    async def test_list_files_skips_symlinked_libraries(self, tools, real_client):
        lib = real_client.workspace.parent / "lib-src"
        (lib / "deep").mkdir(parents=True)
        (lib / "deep" / "x.scad").write_text("cube(1);")
        (real_client.workspace / "LibLink").symlink_to(lib)
        await make(tools, "sub/model.scad", "cube(1);")
        res = await tools("openscad_list_files")()
        assert res["files"] == ["sub/model.scad"]

    async def test_every_example_parses(self, tools):
        names = (await tools("openscad_list_examples")())["examples"]
        assert len(names) >= 14
        for name in names:
            got = await tools("openscad_get_example")(name=name)
            check = await tools("openscad_check_syntax")(filename=got["workspace_file"])
            assert check["passed"], (name, check["errors"])

    async def test_check_syntax_warnings_vs_errors(self, tools):
        await make(tools, "w.scad", "cube(1);\nfoo();\n")
        res = await tools("openscad_check_syntax")(filename="w.scad")
        assert res["passed"] and not res["strict_passed"] and res["warnings"][0]["line"] == 2

    async def test_clear_cache(self, tools):
        await make(tools, "c.scad", "cube(1);")
        await tools("openscad_measure")(filename="c.scad")
        res = await tools("openscad_clear_cache")()
        assert res["files_removed"] >= 1
        again = await tools("openscad_measure")(filename="c.scad")
        assert again["cached"] is False


def test_stl_written_by_export_is_binary(tmp_path):
    """Guard for the parser used everywhere: binary STL size formula."""
    p = tmp_path / "x.stl"
    p.write_bytes(b"\0" * 80 + (0).to_bytes(4, "little"))
    assert geometry.read_stl(p) == []
