"""v0.4: one shared render per model, pure-Python sections, interference that
survives meshes CGAL refuses, compact results, and a sturdier server.

Numeric checks come with a perturbation (change the input, show the output
moves), so a path that does nothing cannot pass.
"""

import asyncio
import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from openscad_mcp import diagnostics, geometry
from openscad_mcp.client import OpenSCADClient
from openscad_mcp.tools._common import compact_diag

# Two cubes sharing one vertical edge: a non-manifold mesh CGAL refuses to import.
EDGE_CUBES = "cube(10); translate([10, 10, 0]) cube(10);"
BLOCK = "translate([-4, -4, 1]) cube([30, 8, 2]);"  # overlaps the first cube by 10 x 4 x 2


async def make(tools, name, code):
    await tools("openscad_create")(filename=name, code=code)


def _meta(content: list) -> dict:
    return json.loads([c for c in content if isinstance(c, str)][-1])


def _images(content: list) -> list:
    return [c for c in content if type(c).__name__ == "Image"]


def _count_runs(client: OpenSCADClient):
    calls = []
    real = client.run

    async def counting(args, timeout=None):
        calls.append(args)
        return await real(args, timeout=timeout)

    return calls, patch.object(client, "run", counting)


class TestSharedRender:
    async def test_export_and_get_info_reuse_the_measured_mesh(self, tools, real_client):
        await make(tools, "c.scad", "size = 4;\ncube(size);\n")
        await tools("openscad_measure")(filename="c.scad")
        calls, counting = _count_runs(real_client)
        with counting:
            exp = await tools("openscad_export")(filename="c.scad", output_filename="out/c.stl")
            info = await tools("openscad_get_info")(filename="c.scad")
        assert calls == [] and exp["cached"] is True and info["cached"] is True
        assert exp["mesh"]["bbox"]["size"] == [4, 4, 4]
        assert info["summary"]["geometry"] and "stderr" not in info
        # Perturb: other parameters are another mesh, rendered once.
        with counting:
            big = await tools("openscad_export")(filename="c.scad", output_filename="c9.stl", parameters={"size": 9})
        assert len(calls) == 1 and big["cached"] is False and big["mesh"]["bbox"]["size"] == [9, 9, 9]

    async def test_parallel_calls_share_one_render(self, tools, real_client):
        await make(tools, "p.scad", "sphere(r=5, $fn=24);")
        calls, counting = _count_runs(real_client)
        with counting:
            results = await asyncio.gather(
                tools("openscad_measure")(filename="p.scad"),
                tools("openscad_mass_properties")(filename="p.scad"),
                tools("openscad_print_report")(filename="p.scad"),
            )
        assert len(calls) == 1
        assert results[0]["volume"] == pytest.approx(results[1]["volume_mm3"])
        # Perturb: use_cache=False always renders.
        with counting:
            await tools("openscad_measure")(filename="p.scad", use_cache=False)
        assert len(calls) == 2

    async def test_cancelling_every_caller_stops_the_shared_render(self, real_client, tmp_path):
        started, cancelled = asyncio.Event(), asyncio.Event()

        async def slow(args, timeout=None):
            started.set()
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                cancelled.set()
                raise
            return 0, "", ""

        src = real_client.workspace / "s.scad"
        src.write_text("cube(1);")
        real_client.ensure_ready()
        with patch.object(real_client, "run", slow):
            waiters = [asyncio.ensure_future(real_client.render_mesh(src)) for _ in range(2)]
            await started.wait()
            waiters[0].cancel()
            await asyncio.sleep(0.05)
            assert not cancelled.is_set()  # one caller is still waiting
            waiters[1].cancel()
            await asyncio.wait_for(cancelled.wait(), 5)
            for _ in range(3):
                await asyncio.sleep(0)  # let the task's done-callback run
        assert real_client._flights == {}

    async def test_edit_during_digest_is_never_cached(self, tools, real_client):
        """The race found in v0.3: an edit between the staleness check and the
        digest stored the new file's digest next to the old mesh."""
        await make(tools, "r.scad", "cube(2);")
        src = real_client.workspace / "r.scad"
        real_digest, real_run = real_client._digest, real_client.run
        rendered, edited = [], []

        async def run(args, timeout=None):
            out = await real_run(args, timeout=timeout)
            rendered.append(True)
            return out

        def digest_after_edit(paths):
            if rendered and not edited:  # the digest taken after the render
                edited.append(True)
                src.write_text("cube(5);")
            return real_digest(paths)

        with patch.object(real_client, "_digest", digest_after_edit), patch.object(real_client, "run", run):
            first = await tools("openscad_measure")(filename="r.scad")
        assert first["volume"] == 8 and edited
        again = await tools("openscad_measure")(filename="r.scad")
        assert again["cached"] is False and again["volume"] == 125

    async def test_cache_key_covers_library_path_and_ignores_parameter_order(self, real_client, tmp_path):
        real_client.ensure_ready()
        src = real_client.workspace / "k.scad"
        k1 = real_client._cache_key(src, {"a": 1, "b": 2}, [])
        assert k1 == real_client._cache_key(src, {"b": 2, "a": 1}, [])
        assert k1 != real_client._cache_key(src, {"a": 1, "b": 3}, [])
        (tmp_path / "other-libs").mkdir()
        other = OpenSCADClient(workspace=real_client.workspace, libraries=tmp_path / "other-libs",
                               cache_dir=real_client.cache_dir)
        other.binary, other.features, other._probed = real_client.binary, real_client.features, True
        assert other._cache_key(src, {"a": 1, "b": 2}, []) != k1

    async def test_eviction_keeps_recent_and_live_entries(self, tools, real_client):
        for i in range(3):
            await make(tools, f"e{i}.scad", f"cube({i + 1});")
            await tools("openscad_measure")(filename=f"e{i}.scad")
        mesh = real_client.cache_dir / "mesh"
        entries = sorted(mesh.iterdir())
        assert len(entries) == 3
        old = time.time() - 7200
        for e in entries[:2]:
            os.utime(e / "meta.json", (old, old))
        orphan = entries[2] / "mesh.deadbeef0000.stl"
        orphan.write_bytes(b"x" * 10)
        os.utime(orphan, (old, old))
        res = real_client.evict(max_bytes=0)  # over the cap: drop all idle entries
        assert res["entries_removed"] == 2 and sorted(mesh.iterdir()) == [entries[2]]
        assert not orphan.exists()
        assert (await tools("openscad_measure")(filename="e2.scad"))["cached"] is True


class TestSection:
    async def test_non_manifold_mesh_still_gets_a_section(self, tools):
        """v0.3 reported 'The plane does not cut the model' here (CGAL refused the mesh)."""
        await make(tools, "teeth.scad", "cylinder(r=10, h=4, $fn=32);\n"
                   "for (a = [0:90:270]) rotate(a) translate([11.5, 0, 0]) cylinder(r=1.5, h=4, $fn=16);")
        meta = _meta(await tools("openscad_section")(filename="teeth.scad", offset=2, return_image=False))
        assert meta["regions"] == 5 and meta["area"] > 300
        assert not (await tools("openscad_measure")(filename="teeth.scad"))["watertight"]

    async def test_faces_holes_islands_and_axes(self, tools):
        await make(tools, "island.scad", "difference() { cube([30, 30, 10]); translate([5, 5, -1]) cube([20, 20, 12]); }\n"
                   "translate([12, 12, 0]) cube([6, 6, 10]);")
        cut = lambda **kw: tools("openscad_section")(filename="island.scad", return_image=False, **kw)  # noqa: E731
        mid = _meta(await cut(axis="z", offset=5))
        assert mid["area"] == pytest.approx(900 - 400 + 36) and mid["regions"] == 2
        assert mid["bbox_2d"] == {"min": [0, 0], "max": [30, 30], "size": [30, 30]}
        top, bottom = _meta(await cut(axis="z", offset=10)), _meta(await cut(axis="z", offset=0))
        assert top["area"] == bottom["area"] == mid["area"] and "face" in top["note"] and "face" in bottom["note"]
        side = _meta(await cut(axis="y", offset=15))  # plane (x, -z): two walls plus the island
        assert side["area"] == pytest.approx(2 * 5 * 10 + 6 * 10) and side["regions"] == 3
        assert side["bbox_2d"]["min"] == [0, -10] and side["bbox_2d"]["max"] == [30, 0]
        assert _meta(await cut(axis="x", offset=40))["note"] == "The plane does not cut the model."

    async def test_section_image_is_returned(self, tools):
        await make(tools, "ring.scad", "difference() { cylinder(d=20, h=5, $fn=48); translate([0, 0, -1]) cylinder(d=10, h=7, $fn=48); }")
        out = await tools("openscad_section")(filename="ring.scad", offset=2.5, width=200, height=150)
        meta = _meta(out)
        assert len(_images(out)) == 1 and Path(meta["image"]).read_bytes()[:4] == b"\x89PNG"


class TestInterference:
    async def test_non_manifold_part_falls_back_to_ray_sampling(self, tools):
        """v0.3 answered 'touching_or_near', volume 0, for this overlapping pair."""
        await make(tools, "edges.scad", EDGE_CUBES)
        await make(tools, "block.scad", BLOCK)
        hit = await tools("openscad_interference")(file_a="edges.scad", file_b="block.scad")
        assert hit["status"] == "interference" and hit["method"] == "ray_sampled"
        assert hit["interference_volume"] == pytest.approx(80, rel=1e-6)
        assert hit["interference_bbox"]["min"][2] == pytest.approx(1) and "ray sampling" in hit["note"]
        # Perturb: move the block off the cubes (bboxes still overlap the second cube's).
        await make(tools, "block.scad", "translate([12, 11, 1]) cube([2, 2, 2]);")
        moved = await tools("openscad_interference")(file_a="edges.scad", file_b="block.scad")
        assert moved["interference_volume"] == pytest.approx(8, rel=1e-6)

    def test_ray_overlap_matches_exact_volumes(self):
        cube = lambda lo, hi: [(a, b, c) for a, b, c in _box(lo, hi)]  # noqa: E731
        a, b = cube((0, 0, 0), (10, 10, 10)), cube((5, 5, 5), (15, 15, 15))
        bb = lambda t: (tuple(min(p[i] for tri in t for p in tri) for i in range(3)),  # noqa: E731
                        tuple(max(p[i] for tri in t for p in tri) for i in range(3)))
        est = geometry.ray_overlap(a, b, bb(a), bb(b))
        assert est["status"] == "interference" and est["volume"] == pytest.approx(125)
        apart = cube((20, 0, 0), (30, 10, 10))
        assert geometry.ray_overlap(a, apart, bb(a), bb(apart))["status"] == "clear"
        open_top = a[:-2]  # remove the two top triangles: an open mesh
        leaky = geometry.ray_overlap(open_top, b, bb(open_top), bb(b))
        assert leaky["invalid_rays"] > 0 and leaky["status"] in ("indeterminate", "interference")


def _box(lo, hi):
    """Outward-oriented triangles of an axis-aligned box."""
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    quads = [(0, 3, 2, 1), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)]
    tris = []
    for a, b, c, d in quads:
        tris += [(v[a], v[b], v[c]), (v[a], v[c], v[d])]
    return tris


class TestPreview:
    async def test_render_true_works_on_2021(self, tools):
        """v0.3 put --render last; 2021.01 took the input path as its value and failed."""
        await make(tools, "r.scad", "difference() { cube(10, center=true); sphere(6.5, $fn=24); }")
        out = await tools("openscad_preview")(filename="r.scad", render=True, width=160, height=120)
        assert len(_images(out)) == 1

    async def test_errors_return_no_images_and_view_sizes(self, tools):
        await make(tools, "bad.scad", 'cube(1);\nassert(false, "nope");\n')
        out = await tools("openscad_preview")(filename="bad.scad", views=["isometric", "top"])
        meta = _meta(out)
        assert _images(out) == [] and meta["errors"] and "not returned" in meta["note"]
        assert len(meta["errors"]) == 1  # reported once, not once per view
        await make(tools, "ok.scad", "cube(1);")
        many = _meta(await tools("openscad_preview")(filename="ok.scad", views=["isometric", "top"]))
        one = _meta(await tools("openscad_preview")(filename="ok.scad"))
        assert [i["size"] for i in many["images"]] == [[512, 384], [512, 384]]
        assert one["images"][0]["size"] == [1024, 768]


class TestCompactResults:
    def test_repeated_messages_merge_and_echo_is_capped(self):
        text = "\n".join(
            ["WARNING: Ignoring 2D child object for 3D operation in file m.scad, line %d" % n for n in (5, 9, 12)]
            + ["WARNING: Ignoring unknown module 'foo' in file m.scad, line 3",
               "ERROR: Assertion 'false' failed in file m.scad, line 20",
               "TRACE: called by 'assert' in file m.scad, line 20",
               "DEPRECATED: The assign() module will be removed in file m.scad, line 1",
               "DEPRECATED: The assign() module will be removed in file m.scad, line 1"]
            + ["ECHO: %d" % i for i in range(30)]
        )
        d = compact_diag(diagnostics.parse_output(text))
        assert d["warnings"][0] == {"message": "WARNING: Ignoring 2D child object for 3D operation".split(": ", 1)[1],
                                    "file": "m.scad", "lines": [5, 9, 12]}
        assert d["warnings"][1] == {"message": "Ignoring unknown module 'foo'", "file": "m.scad", "line": 3}
        assert d["errors"][0]["line"] == 20 and d["errors"][0]["trace"]
        assert d["notes"] == ["DEPRECATED: The assign() module will be removed in file m.scad, line 1"]
        assert len(d["echo"]) == 10 and d["echo_omitted"] == 20

    async def test_check_syntax_reports_deprecations_without_a_console_dump(self, tools):
        await make(tools, "dep.scad", "assign(x = 1) cube(x);\n")
        res = await tools("openscad_check_syntax")(filename="dep.scad")
        assert "stderr" not in res and any("DEPRECATED" in n for n in res["notes"])
        assert res["errors"] == [] and res["passed"]

    async def test_large_examples_are_copied_not_inlined(self, tools):
        big = await tools("openscad_get_example")(name="factory_arduino_assembly")
        assert "content" not in big and big["bytes"] > 50_000 and "openscad_read" in big["note"]
        forced = await tools("openscad_get_example")(name="factory_arduino_assembly", include_content=True)
        assert len(forced["content"]) > 50_000
        small = await tools("openscad_get_example")(name="box")
        assert small["content"].strip()


class TestServerRobustness:
    def test_unanswered_probe_is_retried_not_cached(self, real_client):
        with patch("openscad_mcp.client._probe_version", return_value=""):
            real_client.ensure_ready()
        assert real_client._probed is False and real_client._probe_retry_at > time.monotonic()
        real_client._probe_retry_at = 0.0
        real_client.ensure_ready()
        assert real_client._probed is True and real_client.features.version_text != "unknown"

    async def test_workspace_error_is_a_tool_error_not_a_crash(self, tools, real_client, tool_error, tmp_path):
        blocker = tmp_path / "file"
        blocker.write_text("not a directory")
        real_client.workspace = blocker / "ws"
        err = await tool_error(tools("openscad_list_files")())
        assert "Not a directory" in err["error"] or "ws" in err["error"]

    async def test_kill_children_stops_running_processes(self, real_client):
        real_client.binary, real_client._probed = "/bin/sleep", True
        task = asyncio.ensure_future(real_client.run(["30"]))
        for _ in range(100):
            if real_client._procs:
                break
            await asyncio.sleep(0.02)
        real_client.kill_children()
        rc, _, _ = await asyncio.wait_for(task, 5)
        assert rc != 0 and not real_client._procs
