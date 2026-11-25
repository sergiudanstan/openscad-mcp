"""The server through a real MCP client session (in-memory transport)."""

import base64
import json

import pytest
from mcp import Client

from openscad_mcp import server as server_module

EXPECTED_TOOLS = {
    "openscad_create", "openscad_read", "openscad_edit", "openscad_get_parameters",
    "openscad_export", "openscad_preview", "openscad_render_animated", "openscad_get_info",
    "openscad_measure", "openscad_mass_properties", "openscad_interference", "openscad_section",
    "openscad_print_report", "openscad_eval",
    "openscad_list_files", "openscad_cheatsheet", "openscad_version", "openscad_check_syntax",
    "openscad_list_examples", "openscad_get_example", "openscad_list_libraries",
    "openscad_library_info", "openscad_clear_cache",
}
READ_ONLY = {"openscad_read", "openscad_measure", "openscad_check_syntax", "openscad_list_files", "openscad_eval"}


@pytest.fixture()
def isolated_server(real_client, monkeypatch):
    """Point the server's lifespan client at the test workspace."""
    monkeypatch.setattr(server_module, "OpenSCADClient", lambda: real_client)
    return server_module.mcp


async def test_tool_list_annotations_and_instructions(isolated_server):
    async with Client(isolated_server) as client:
        init_tools = (await client.list_tools()).tools
        names = {t.name for t in init_tools}
        assert names == EXPECTED_TOOLS
        for t in init_tools:
            assert t.annotations is not None, t.name
            if t.name in READ_ONLY:
                assert t.annotations.read_only_hint is True, t.name
    assert "openscad_measure" in (isolated_server.instructions or "")


async def test_preview_image_and_structured_results(isolated_server):
    async with Client(isolated_server) as client:
        r = await client.call_tool("openscad_create", {"filename": "c.scad", "code": "cube(7);"})
        assert not r.is_error and r.structured_content["etag"]
        m = await client.call_tool("openscad_measure", {"filename": "c.scad"})
        assert m.structured_content["volume"] == 343
        assert json.loads(m.content[0].text)["volume"] == 343  # text mirror for older clients
        p = await client.call_tool("openscad_preview", {"filename": "c.scad", "width": 200, "height": 150})
        images = [c for c in p.content if c.type == "image"]
        assert len(images) == 1 and images[0].mime_type == "image/png"
        assert base64.b64decode(images[0].data)[:4] == b"\x89PNG"


async def test_errors_are_flagged(isolated_server):
    async with Client(isolated_server) as client:
        r = await client.call_tool("openscad_read", {"filename": "../../etc/passwd"})
        assert r.is_error and "Path traversal" in r.content[0].text
        r = await client.call_tool("openscad_measure", {"filename": "missing.scad"})
        assert r.is_error and "File not found" in r.content[0].text
