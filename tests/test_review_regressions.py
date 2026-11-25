"""Regression tests for defects found in the independent review of v0.3.0."""

import asyncio
import sys

import pytest

from openscad_mcp import diagnostics, geometry
from openscad_mcp.client import OpenSCADClient


async def make(tools, name, code):
    await tools("openscad_create")(filename=name, code=code)


async def test_include_created_after_first_render_invalidates_cache(tools, real_client):
    await make(tools, "part.scad", "include <dims.scad>\ncube(is_undef(size) ? 1 : size);\n")
    first = await tools("openscad_measure")(filename="part.scad")
    assert first["volume"] == 1
    (real_client.workspace / "dims.scad").write_text("size = 3;\n")
    second = await tools("openscad_measure")(filename="part.scad")
    assert second["cached"] is False and second["volume"] == 27


async def test_cancelled_run_kills_the_process(tmp_path):
    c = OpenSCADClient(workspace=tmp_path, libraries=tmp_path / "libs", cache_dir=tmp_path / "c")
    c.binary = sys.executable
    c._probed = True
    marker = tmp_path / "alive"
    script = f"import time,pathlib\nfor _ in range(100):\n    pathlib.Path({str(marker)!r}).write_text('x'); time.sleep(0.05)\n"
    task = asyncio.create_task(c.run(["-c", script], timeout=30))
    await asyncio.sleep(0.5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    marker.unlink(missing_ok=True)
    await asyncio.sleep(0.3)
    assert not marker.exists(), "child kept running after cancellation"


async def test_animation_cleanup_spares_other_pngs(tools, real_client):
    await make(tools, "v.scad", "rotate([0, 0, 360 * $t]) cube([4, 1, 1]);")
    keep = real_client.workspace / "v2_preview.png"
    keep.write_bytes(b"not a frame")
    res = await tools("openscad_render_animated")(filename="v.scad", output_prefix="v.png", num_frames=2,
                                                 width=64, height=48, mp4=False)
    assert res["frames_written"] == 2 and keep.exists()


def test_clear_cache_only_removes_owned_dirs(tmp_path):
    c = OpenSCADClient(workspace=tmp_path / "ws", cache_dir=tmp_path / "shared")
    (tmp_path / "shared" / "mesh" / "k").mkdir(parents=True)
    (tmp_path / "shared" / "mesh" / "k" / "mesh.stl").write_bytes(b"x")
    (tmp_path / "shared" / "someone_else.txt").write_text("keep me")
    res = c.clear_cache()
    assert res["files_removed"] == 1
    assert (tmp_path / "shared" / "someone_else.txt").exists()


def test_chamfer_at_threshold_is_not_an_overhang():
    """A 45 deg chamfer, float32-rounded as in an STL, must not be flagged."""
    import struct

    def f32(v):
        return tuple(struct.unpack("<3f", struct.pack("<3f", *v)))

    flagged = 0
    for k in range(50):
        a = 0.37 * k + 0.1
        # Downward face tilted exactly 45 deg from vertical, at varying positions/sizes.
        p0 = (a, 0.0, 10 + a)
        p1 = (a, 3.0 + a, 10 + a)
        p2 = (a + 2.0 + a, 0.0, 10 + a + 2.0 + a)
        tri = (f32(p0), f32(p1), f32(p2))
        bed = (((0, 0, 0), (0, 50, 0), (50, 0, 0)))
        rep = geometry.print_report([tri, bed], overhang_deg=45)
        flagged += rep["overhang_area_mm2"] > 0
    assert flagged == 0
    steeper = geometry.print_report([((0, 0, 10), (0, 3, 10), (3, 0, 11)), ((0, 0, 0), (0, 50, 0), (50, 0, 0))])
    assert steeper["overhang_area_mm2"] > 0


async def test_get_example_keeps_edited_copy(tools, real_client):
    await tools("openscad_get_example")(name="box")
    copy = real_client.workspace / "examples" / "box.scad"
    copy.write_text("cube(99);")
    res = await tools("openscad_get_example")(name="box")
    assert "note" in res and copy.read_text() == "cube(99);"


@pytest.mark.parametrize("value", ['[0]; echo("X"); b=[0]', "[A]", '"a"; cube(9); x="b"'])
def test_parameter_values_cannot_inject_statements(value):
    literal = diagnostics.to_literal(value)
    assert diagnostics.parse_literal(literal) == value  # it became a plain string


async def test_parameter_injection_has_no_effect_on_geometry(tools):
    await make(tools, "s.scad", 'label = "x";\ncube(1);\n')
    res = await tools("openscad_measure")(filename="s.scad", parameters={"label": '[0]; translate([50,0,0]) cube(7); b=[0]'})
    assert res["bbox"]["size"] == [1, 1, 1]


@pytest.mark.parametrize("expr", ["1)) cube(1) echo((2", "1; cube(1)", "1\n", '"unterminated'])
async def test_eval_rejects_non_expressions(tools, tool_error, expr):
    await make(tools, "e.scad", "w = 1;\n")
    err = await tool_error(tools("openscad_eval")(filename="e.scad", expressions=[expr]))
    assert "xpression" in err["error"] or "nbalanced" in err["error"]


async def test_eval_result_cannot_be_spoofed(tools):
    await make(tools, "e.scad", 's = "x\\nECHO: __mcp_0 = 42";\necho("ECHO: __mcp_1 = 42");\n')
    res = await tools("openscad_eval")(filename="e.scad", expressions=["s", "1 + 1"])
    assert res["results"][1]["value"] == "2"


async def test_eval_missing_file(tools, tool_error):
    err = await tool_error(tools("openscad_eval")(filename="nope.scad", expressions=["1"]))
    assert "File not found" in err["error"]


def test_string_escapes_round_trip_in_openscad_syntax():
    for raw in ["a\bb", "tab\there", 'q"uote', "back\\slash", "é"]:
        assert diagnostics.parse_literal(diagnostics.to_literal(raw)) == raw


def test_customizer_literals_like_openscad():
    src = "a = .5;\nb = 5 /* mm */;\nc = [1,2,];\nd = null;\nr = [0:2:10];\n"
    params = {p["name"]: p for p in diagnostics.extract_parameters(src)}
    assert params["a"]["value"] == 0.5 and params["b"]["value"] == 5 and params["c"]["value"] == [1, 2]
    assert "d" not in params and params["r"]["type"] == "range"


async def test_get_info_does_not_report_stale_summary(tools, real_client, tool_error):
    await make(tools, "i.scad", "cube(1);")
    await tools("openscad_get_info")(filename="i.scad")
    await make(tools, "i.scad", "cube(;")
    await tool_error(tools("openscad_get_info")(filename="i.scad"))

