"""Tests that run the real OpenSCAD CLI and the registered MCP tools end to end.

CI installs OpenSCAD and sets REQUIRE_OPENSCAD=1, so a missing binary fails there
instead of silently skipping.
"""

import json
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from mcp.server.mcpserver import MCPServer

from openscad_mcp.client import OpenSCADClient
from openscad_mcp.tools.design_tools import register_design_tools
from openscad_mcp.tools.library_tools import register_library_tools
from openscad_mcp.tools.render_tools import register_render_tools


@pytest.fixture()
def real_client(tmp_path: Path) -> OpenSCADClient:
    binary = shutil.which("openscad")
    if binary is None:
        if os.environ.get("REQUIRE_OPENSCAD"):
            pytest.fail("REQUIRE_OPENSCAD is set but openscad is not on PATH")
        pytest.skip("openscad not installed")
    ws = tmp_path / "ws"
    ws.mkdir()
    c = OpenSCADClient(workspace=ws)
    c.libraries = tmp_path / "no-libraries"  # keep the user's installed libraries out of the test
    c.binary = binary
    return c


@pytest.fixture()
def tools(real_client: OpenSCADClient):
    mcp = MCPServer("test")
    register_design_tools(mcp)
    register_render_tools(mcp)
    register_library_tools(mcp)
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"client": real_client}
    return lambda name: (lambda **kw: mcp._tool_manager._tools[name].fn(ctx, **kw))


class TestPathConfinement:
    def test_sibling_with_same_prefix_rejected(self, real_client: OpenSCADClient) -> None:
        sibling = real_client.workspace.parent / (real_client.workspace.name + "-evil")
        sibling.mkdir()
        with pytest.raises(ValueError, match="Path traversal not allowed"):
            real_client.resolve_path(f"../{sibling.name}/x.scad")

    @pytest.mark.asyncio
    async def test_create_refuses_to_write_outside(self, tools, real_client: OpenSCADClient) -> None:
        result = json.loads(await tools("openscad_create")(filename="../escape.scad", code="cube(1);"))
        assert "Path traversal not allowed" in result["error"]
        assert not (real_client.workspace.parent / "escape.scad").exists()


class TestRealOpenSCAD:
    @pytest.mark.asyncio
    async def test_create_read_roundtrip(self, tools) -> None:
        await tools("openscad_create")(filename="a.scad", code="cube(3);")
        result = json.loads(await tools("openscad_read")(filename="a.scad"))
        assert result["content"] == "cube(3);"

    @pytest.mark.asyncio
    async def test_check_syntax_accepts_valid_and_rejects_invalid(self, tools) -> None:
        await tools("openscad_create")(filename="ok.scad", code="cube(10);")
        await tools("openscad_create")(filename="bad.scad", code="cube(;")
        ok = json.loads(await tools("openscad_check_syntax")(filename="ok.scad"))
        bad = json.loads(await tools("openscad_check_syntax")(filename="bad.scad"))
        assert ok["passed"] is True
        assert bad["passed"] is False and bad["errors"]

    @pytest.mark.asyncio
    async def test_export_stl_has_geometry(self, tools, real_client: OpenSCADClient) -> None:
        await tools("openscad_create")(filename="box.scad", code="size = 5; cube(size);")
        result = json.loads(await tools("openscad_export")(filename="box.scad", output_format="stl"))
        stl = Path(result["path"])
        assert stl.parent == real_client.workspace.resolve()
        text = stl.read_text()
        assert text.startswith("solid") and text.count("facet normal") == 12  # a cube is 12 triangles

    @pytest.mark.asyncio
    async def test_export_parameter_override_changes_geometry(self, tools) -> None:
        await tools("openscad_create")(filename="p.scad", code="size = 5; cube(size);")
        result = json.loads(
            await tools("openscad_export")(
                filename="p.scad", output_format="stl", output_filename="p20.stl", parameters={"size": "20"}
            )
        )
        coords = [
            float(v)
            for line in Path(result["path"]).read_text().splitlines()
            if line.strip().startswith("vertex")
            for v in line.split()[1:]
        ]
        assert max(coords) == 20.0  # not the default size of 5

    @pytest.mark.asyncio
    async def test_export_rejects_unknown_format(self, tools) -> None:
        await tools("openscad_create")(filename="b.scad", code="cube(1);")
        result = json.loads(await tools("openscad_export")(filename="b.scad", output_format="exe"))
        assert "Unsupported format" in result["error"]

    @pytest.mark.asyncio
    async def test_get_info_reports_geometry(self, tools) -> None:
        await tools("openscad_create")(filename="i.scad", code="cube(2);")
        result = json.loads(await tools("openscad_get_info")(filename="i.scad"))
        assert "error" not in result
        assert result["summary"]["geometry"]


class TestLibraryInfoConfinement:
    @pytest.mark.asyncio
    async def test_library_info_reads_installed_library(self, tools, real_client: OpenSCADClient) -> None:
        lib = real_client.libraries / "MyLib"
        lib.mkdir(parents=True)
        (lib / "part.scad").write_text("module p() cube(1);")
        (lib / "README.md").write_text("hello lib")
        result = json.loads(await tools("openscad_library_info")(library_name="MyLib"))
        assert result["total_scad_files"] == 1 and result["readme_excerpt"] == "hello lib"

    @pytest.mark.asyncio
    async def test_library_info_refuses_paths_outside_the_library_directory(
        self, tools, real_client: OpenSCADClient
    ) -> None:
        real_client.libraries.mkdir(parents=True)
        secret = real_client.libraries.parent / "secret-dir"
        secret.mkdir()
        (secret / "README.md").write_text("TOP SECRET")
        result = json.loads(await tools("openscad_library_info")(library_name="../secret-dir"))
        assert "TOP SECRET" not in json.dumps(result)
        assert "error" in result
