"""OpenSCAD MCP Server."""
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.mcpserver import MCPServer

from openscad_mcp import __version__
from openscad_mcp.client import OpenSCADClient
from openscad_mcp.tools.analysis_tools import register_analysis_tools
from openscad_mcp.tools.design_tools import register_design_tools
from openscad_mcp.tools.library_tools import register_library_tools
from openscad_mcp.tools.render_tools import register_render_tools

logger = logging.getLogger(__name__)

INSTRUCTIONS = """\
OpenSCAD modelling server (units: mm, Z up). All paths are relative to the workspace.

Loop that works: openscad_create -> openscad_check_syntax -> openscad_preview
(returns images; use views=["isometric","front","top","right"]) -> openscad_measure
(exact bbox/volume/watertight) -> fix with openscad_edit (old_string/new_string) ->
openscad_export. Judge sizes with openscad_measure, not by eye.

- OpenSCAD exits 0 on failed asserts and unknown modules: always read `errors`
  and `warnings` in tool results; check_syntax `passed` already accounts for this.
- Parameters are typed JSON: {"width": 40, "label": "A", "holes": [3, 5], "solid": true}.
  openscad_get_parameters lists a model's customizer variables.
- Engineering: openscad_mass_properties (material/density), openscad_interference
  (two parts), openscad_section (cut plane, wall thickness), openscad_print_report
  (overhangs, bed contact, build volume), openscad_eval (expressions in model scope).
- Renders are cached by file content and includes; repeated analysis is fast.
- Overlap coplanar faces in difference()/union() by 0.01 mm to stay manifold.
"""


@asynccontextmanager
async def server_lifespan(server: MCPServer) -> AsyncIterator[dict]:
    client = OpenSCADClient()
    try:
        client.ensure_ready()
        logger.info("OpenSCAD MCP %s starting — binary: %s (%s, backend %s)", __version__,
                    client.binary, client.features.version_text, client.features.backend)
    except FileNotFoundError as exc:
        # Keep serving: tools report the problem instead of the server dying silently.
        logger.error("%s", exc)
    try:
        yield {"client": client}
    finally:
        logger.info("OpenSCAD MCP server stopped")


mcp = MCPServer("openscad", instructions=INSTRUCTIONS, lifespan=server_lifespan)

register_design_tools(mcp)
register_render_tools(mcp)
register_analysis_tools(mcp)
register_library_tools(mcp)
