"""Tests for openscad_mcp tools."""

import json
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from openscad_mcp.client import OpenSCADClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_workspace(tmp_path: Path) -> Path:
    """Return a temporary directory to use as a workspace."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


@pytest.fixture()
def client(tmp_workspace: Path) -> OpenSCADClient:
    """Return an OpenSCADClient pointed at a temporary workspace."""
    c = OpenSCADClient(workspace=tmp_workspace)
    c.binary = shutil.which("openscad") or "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"
    return c


# ---------------------------------------------------------------------------
# OpenSCADClient.resolve_path
# ---------------------------------------------------------------------------

class TestResolvePath:
    def test_valid_filename(self, client: OpenSCADClient) -> None:
        """A plain filename resolves inside the workspace."""
        path = client.resolve_path("model.scad")
        assert path.parent == client.workspace.resolve()
        assert path.name == "model.scad"

    def test_nested_valid_path(self, client: OpenSCADClient) -> None:
        """A relative subdirectory path resolves inside the workspace."""
        path = client.resolve_path("sub/model.scad")
        assert str(path).startswith(str(client.workspace.resolve()))

    def test_path_traversal_rejected(self, client: OpenSCADClient) -> None:
        """Path traversal attempts are rejected with ValueError."""
        with pytest.raises(ValueError, match="Path traversal not allowed"):
            client.resolve_path("../../etc/passwd")

    def test_absolute_outside_rejected(self, client: OpenSCADClient) -> None:
        """An absolute path outside workspace is rejected."""
        with pytest.raises(ValueError, match="Path traversal not allowed"):
            client.resolve_path("/etc/passwd")


# ---------------------------------------------------------------------------
# OpenSCADClient.discover_binary
# ---------------------------------------------------------------------------

class TestDiscoverBinary:
    def test_finds_on_path(self, tmp_workspace: Path) -> None:
        """discover_binary returns path when openscad is on PATH."""
        fake_binary = tmp_workspace / "openscad"
        fake_binary.write_text("#!/bin/sh\necho ok\n")
        fake_binary.chmod(0o755)

        with patch("shutil.which", return_value=str(fake_binary)):
            c = OpenSCADClient(workspace=tmp_workspace)
            result = c.discover_binary()
        assert result == str(fake_binary)

    def test_raises_when_not_found(self, tmp_workspace: Path) -> None:
        """discover_binary raises FileNotFoundError if nothing found."""
        with (
            patch("shutil.which", return_value=None),
            patch("os.path.isfile", return_value=False),
        ):
            c = OpenSCADClient(workspace=tmp_workspace)
            with pytest.raises(FileNotFoundError, match="OpenSCAD binary not found"):
                c.discover_binary()

    @pytest.mark.skipif(
        shutil.which("openscad") is None
        and not Path("/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD").is_file(),
        reason="OpenSCAD not installed on this system",
    )
    def test_real_binary_found(self, tmp_workspace: Path) -> None:
        """discover_binary finds the real OpenSCAD binary when installed."""
        c = OpenSCADClient(workspace=tmp_workspace)
        binary = c.discover_binary()
        assert binary  # non-empty string


# ---------------------------------------------------------------------------
# Tool import smoke tests
# ---------------------------------------------------------------------------

class TestToolImports:
    def test_design_tools_importable(self) -> None:
        from openscad_mcp.tools.design_tools import register_design_tools  # noqa: F401

    def test_render_tools_importable(self) -> None:
        from openscad_mcp.tools.render_tools import register_render_tools  # noqa: F401

    def test_library_tools_importable(self) -> None:
        from openscad_mcp.tools.library_tools import register_library_tools  # noqa: F401

    def test_server_importable(self) -> None:
        from openscad_mcp import server  # noqa: F401


# ---------------------------------------------------------------------------
# library_tools — mock-based tests
# ---------------------------------------------------------------------------

def _make_ctx(client: OpenSCADClient) -> MagicMock:
    """Build a minimal mock Context that carries the given client."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"client": client}
    return ctx


class TestLibraryTools:
    """Tests for library_tools functions via direct invocation (mocked ctx)."""

    @pytest.mark.asyncio
    async def test_list_files_empty_workspace(self, client: OpenSCADClient) -> None:
        """openscad_list_files returns empty list for an empty workspace."""
        from openscad_mcp.tools.library_tools import register_library_tools
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        register_library_tools(mcp)

        # Retrieve the registered tool function by calling it directly
        ctx = _make_ctx(client)
        # Access the wrapped function through mcp's tool registry
        tools = {t.name: t for t in mcp._tool_manager.list_tools()}
        list_fn = mcp._tool_manager._tools["openscad_list_files"].fn

        result = json.loads(await list_fn(ctx))
        assert result["files"] == []
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_list_files_finds_scad(self, client: OpenSCADClient) -> None:
        """openscad_list_files finds .scad files placed in the workspace."""
        from openscad_mcp.tools.library_tools import register_library_tools
        from mcp.server.fastmcp import FastMCP

        # Create a dummy .scad file in the workspace
        (client.workspace / "test_model.scad").write_text("cube(1);")

        mcp = FastMCP("test")
        register_library_tools(mcp)
        ctx = _make_ctx(client)

        list_fn = mcp._tool_manager._tools["openscad_list_files"].fn
        result = json.loads(await list_fn(ctx))
        assert "test_model.scad" in result["files"]
        assert result["count"] >= 1

    @pytest.mark.asyncio
    async def test_cheatsheet_content(self, client: OpenSCADClient) -> None:
        """openscad_cheatsheet returns a non-empty string with key terms."""
        from openscad_mcp.tools.library_tools import register_library_tools
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        register_library_tools(mcp)
        ctx = _make_ctx(client)

        cheat_fn = mcp._tool_manager._tools["openscad_cheatsheet"].fn
        result = await cheat_fn(ctx)
        assert isinstance(result, str)
        assert "cube" in result
        assert "sphere" in result
        assert "$fn" in result
        assert "rotate_extrude" in result

    @pytest.mark.asyncio
    async def test_version_mock(self, client: OpenSCADClient) -> None:
        """openscad_version returns JSON with version key."""
        from openscad_mcp.tools.library_tools import register_library_tools
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        register_library_tools(mcp)
        ctx = _make_ctx(client)

        client.version = AsyncMock(return_value="OpenSCAD version 2021.01")

        ver_fn = mcp._tool_manager._tools["openscad_version"].fn
        result = json.loads(await ver_fn(ctx))
        assert "version" in result
        assert "2021.01" in result["version"]

    @pytest.mark.asyncio
    async def test_check_syntax_pass_mock(self, client: OpenSCADClient) -> None:
        """openscad_check_syntax returns passed=True when returncode is 0."""
        from openscad_mcp.tools.library_tools import register_library_tools
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        register_library_tools(mcp)
        ctx = _make_ctx(client)

        # Create the file so resolve_path works
        (client.workspace / "ok.scad").write_text("cube(10);")
        client.check_syntax = AsyncMock(return_value=(0, "", ""))

        syn_fn = mcp._tool_manager._tools["openscad_check_syntax"].fn
        result = json.loads(await syn_fn(ctx, filename="ok.scad"))
        assert result["passed"] is True
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_check_syntax_fail_mock(self, client: OpenSCADClient) -> None:
        """openscad_check_syntax returns passed=False on non-zero returncode."""
        from openscad_mcp.tools.library_tools import register_library_tools
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        register_library_tools(mcp)
        ctx = _make_ctx(client)

        (client.workspace / "bad.scad").write_text("cube(;")  # broken
        client.check_syntax = AsyncMock(
            return_value=(1, "", "ERROR: parse error at line 1")
        )

        syn_fn = mcp._tool_manager._tools["openscad_check_syntax"].fn
        result = json.loads(await syn_fn(ctx, filename="bad.scad"))
        assert result["passed"] is False
        assert len(result["errors"]) >= 1

    @pytest.mark.asyncio
    async def test_list_examples(self, client: OpenSCADClient) -> None:
        """openscad_list_examples returns JSON with examples list."""
        from openscad_mcp.tools.library_tools import register_library_tools
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        register_library_tools(mcp)
        ctx = _make_ctx(client)

        ex_fn = mcp._tool_manager._tools["openscad_list_examples"].fn
        result = json.loads(await ex_fn(ctx))
        # examples directory should exist and contain our 3 files
        assert "examples" in result
        example_names = result["examples"]
        assert "box.scad" in example_names
        assert "gear.scad" in example_names
        assert "vase.scad" in example_names
