"""OpenSCAD MCP Server."""
import asyncio
import logging
import os
import signal
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
(returns images; views=["isometric","front","top","right"] gives 512x384 tiles,
one view at full size shows detail) -> openscad_measure (exact
bbox/volume/watertight) -> fix with openscad_edit (old_string/new_string) ->
openscad_export. Judge sizes with openscad_measure, not by eye.

- OpenSCAD exits 0 on failed asserts and unknown modules: always read `errors`
  and `warnings` in tool results; check_syntax `passed` already accounts for this.
- Parameters are typed JSON: {"width": 40, "label": "A", "holes": [3, 5], "solid": true}.
  openscad_get_parameters lists a model's customizer variables.
- Engineering: openscad_mass_properties (material/density), openscad_interference
  (two parts), openscad_section (cut plane, wall thickness), openscad_print_report
  (overhangs, bed contact, build volume), openscad_eval (expressions in model scope).
- One render per model and parameters is cached and shared by measure, analysis,
  STL export and get_info, so after the first render those calls are fast.
- Overlap coplanar faces in difference()/union() by 0.01 mm to stay manifold.
"""


def _prepare(client: OpenSCADClient) -> None:
    try:
        client.ensure_ready()
        logger.info("OpenSCAD MCP %s starting — binary: %s (%s, backend %s)", __version__,
                    client.binary, client.features.version_text, client.features.backend)
    except OSError as exc:  # includes FileNotFoundError for a missing binary
        # Keep serving: tools report the problem instead of the server dying silently.
        logger.error("%s", exc)


def _install_terminate_handlers(client: OpenSCADClient) -> list[signal.Signals]:
    """On SIGTERM/SIGHUP (a host quitting or restarting the server) kill running
    OpenSCAD processes first; otherwise they outlive the server for minutes."""
    loop = asyncio.get_running_loop()

    def terminate(sig: signal.Signals) -> None:
        client.kill_children()
        signal.signal(sig, signal.SIG_DFL)
        os.kill(os.getpid(), sig)

    installed = []
    for sig in (getattr(signal, "SIGTERM", None), getattr(signal, "SIGHUP", None)):
        if sig is None:
            continue
        try:
            loop.add_signal_handler(sig, terminate, sig)
            installed.append(sig)
        except (NotImplementedError, RuntimeError, ValueError):
            pass  # Windows, or not the main thread
    return installed


@asynccontextmanager
async def server_lifespan(server: MCPServer) -> AsyncIterator[dict]:
    client = OpenSCADClient()
    # Probe the binary in the background: the initialize reply does not wait for
    # it, and a tool call that arrives first simply finishes the probe itself.
    probe = asyncio.get_running_loop().run_in_executor(None, _prepare, client)
    handlers = _install_terminate_handlers(client)
    try:
        yield {"client": client}
    finally:
        loop = asyncio.get_running_loop()
        for sig in handlers:
            loop.remove_signal_handler(sig)
        probe.cancel()
        logger.info("OpenSCAD MCP server stopped")


mcp = MCPServer("openscad", instructions=INSTRUCTIONS, lifespan=server_lifespan)

register_design_tools(mcp)
register_render_tools(mcp)
register_analysis_tools(mcp)
register_library_tools(mcp)
