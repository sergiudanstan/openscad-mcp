"""Tests that run the real OpenSCAD CLI and the registered MCP tools end to end.

CI installs OpenSCAD and sets REQUIRE_OPENSCAD=1, so a missing binary fails there
instead of silently skipping.
"""

import json  # noqa: F401
from pathlib import Path

import pytest

from openscad_mcp import geometry
from openscad_mcp.client import OpenSCADClient


class TestPathConfinement:
    def test_sibling_with_same_prefix_rejected(self, real_client: OpenSCADClient) -> None:
        sibling = real_client.workspace.parent / (real_client.workspace.name + "-evil")
        sibling.mkdir()
        with pytest.raises(ValueError, match="Path traversal not allowed"):
            real_client.resolve_path(f"../{sibling.name}/x.scad")

    @pytest.mark.asyncio
    async def test_create_refuses_to_write_outside(self, tools, tool_error, real_client: OpenSCADClient) -> None:
        result = await tool_error(tools("openscad_create")(filename="../escape.scad", code="cube(1);"))
        assert "Path traversal not allowed" in result["error"]
        assert not (real_client.workspace.parent / "escape.scad").exists()


class TestRealOpenSCAD:
    @pytest.mark.asyncio
    async def test_create_read_roundtrip(self, tools) -> None:
        await tools("openscad_create")(filename="a.scad", code="cube(3);")
        result = (await tools("openscad_read")(filename="a.scad"))
        assert result["content"] == "cube(3);"

    @pytest.mark.asyncio
    async def test_check_syntax_accepts_valid_and_rejects_invalid(self, tools) -> None:
        await tools("openscad_create")(filename="ok.scad", code="cube(10);")
        await tools("openscad_create")(filename="bad.scad", code="cube(;")
        ok = (await tools("openscad_check_syntax")(filename="ok.scad"))
        bad = (await tools("openscad_check_syntax")(filename="bad.scad"))
        assert ok["passed"] is True
        assert bad["passed"] is False and bad["errors"]

    @pytest.mark.asyncio
    async def test_export_stl_has_geometry(self, tools, real_client: OpenSCADClient) -> None:
        await tools("openscad_create")(filename="box.scad", code="size = 5; cube(size);")
        result = (await tools("openscad_export")(filename="box.scad", output_format="stl"))
        stl = Path(result["path"])
        assert stl.parent == real_client.workspace.resolve()
        assert len(geometry.read_stl(stl)) == 12  # a cube is 12 triangles
        assert result["mesh"]["bbox"]["size"] == [5, 5, 5]

    @pytest.mark.asyncio
    async def test_export_parameter_override_changes_geometry(self, tools) -> None:
        await tools("openscad_create")(filename="p.scad", code="size = 5; cube(size);")
        result = (
            await tools("openscad_export")(
                filename="p.scad", output_format="stl", output_filename="p20.stl", parameters={"size": "20"}
            )
        )
        coords = [c for tri in geometry.read_stl(result["path"]) for p in tri for c in p]
        assert max(coords) == 20.0  # not the default size of 5

    @pytest.mark.asyncio
    async def test_export_rejects_unknown_format(self, tools, tool_error) -> None:
        await tools("openscad_create")(filename="b.scad", code="cube(1);")
        result = await tool_error(tools("openscad_export")(filename="b.scad", output_format="exe"))
        assert "Unsupported format" in result["error"]

    @pytest.mark.asyncio
    async def test_get_info_reports_geometry(self, tools) -> None:
        await tools("openscad_create")(filename="i.scad", code="cube(2);")
        result = (await tools("openscad_get_info")(filename="i.scad"))
        assert "error" not in result
        assert result["summary"]["geometry"]


class TestLibraryInfoConfinement:
    @pytest.mark.asyncio
    async def test_library_info_reads_installed_library(self, tools, real_client: OpenSCADClient) -> None:
        lib = real_client.libraries / "MyLib"
        lib.mkdir(parents=True)
        (lib / "part.scad").write_text("module p() cube(1);")
        (lib / "README.md").write_text("hello lib")
        result = (await tools("openscad_library_info")(library_name="MyLib"))
        assert result["total_scad_files"] == 1 and result["readme_excerpt"] == "hello lib"

    @pytest.mark.asyncio
    async def test_library_info_refuses_paths_outside_the_library_directory(
        self, tools, tool_error, real_client: OpenSCADClient
    ) -> None:
        real_client.libraries.mkdir(parents=True)
        secret = real_client.libraries.parent / "secret-dir"
        secret.mkdir()
        (secret / "README.md").write_text("TOP SECRET")
        result = await tool_error(tools("openscad_library_info")(library_name="../secret-dir"))
        assert "TOP SECRET" not in json.dumps(result)
        assert "error" in result
