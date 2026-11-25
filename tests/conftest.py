"""Shared fixtures: a real OpenSCAD client in a temp workspace and direct tool calls."""

import json
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from openscad_mcp.client import OpenSCADClient
from openscad_mcp.tools.analysis_tools import register_analysis_tools
from openscad_mcp.tools.design_tools import register_design_tools
from openscad_mcp.tools.library_tools import register_library_tools
from openscad_mcp.tools.render_tools import register_render_tools


def _binary() -> str | None:
    found = shutil.which("openscad")
    if found:
        return found
    mac = "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"
    return mac if os.path.isfile(mac) else None


@pytest.fixture()
def real_client(tmp_path: Path) -> OpenSCADClient:
    binary = _binary()
    if binary is None:
        if os.environ.get("REQUIRE_OPENSCAD"):
            pytest.fail("REQUIRE_OPENSCAD is set but openscad is not on PATH")
        pytest.skip("openscad not installed")
    ws = tmp_path / "ws"
    ws.mkdir()
    # Keep the user's installed libraries and render cache out of the tests.
    c = OpenSCADClient(workspace=ws, libraries=tmp_path / "no-libraries", cache_dir=tmp_path / "cache")
    c.binary = binary
    return c


def make_tools(client: OpenSCADClient):
    mcp = MCPServer("test")
    register_design_tools(mcp)
    register_render_tools(mcp)
    register_analysis_tools(mcp)
    register_library_tools(mcp)
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"client": client}
    return lambda name: (lambda **kw: mcp._tool_manager._tools[name].fn(ctx, **kw))


@pytest.fixture()
def tools(real_client: OpenSCADClient):
    return make_tools(real_client)


async def _tool_error(coro) -> dict:
    """Await a tool call that must fail; return its error as a dict.

    MCPServer reports any exception from a tool as isError=true; ToolError
    payloads raised via `fail()` are JSON, other exceptions are plain text.
    """
    with pytest.raises(Exception) as exc:
        await coro
    if isinstance(exc.value, ToolError):
        return json.loads(str(exc.value))
    return {"error": str(exc.value)}


@pytest.fixture()
def tool_error():
    return _tool_error
