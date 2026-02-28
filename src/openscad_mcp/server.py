"""OpenSCAD MCP Server."""
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from mcp.server.fastmcp import FastMCP

from openscad_mcp.client import OpenSCADClient
from openscad_mcp.tools.design_tools import register_design_tools
from openscad_mcp.tools.render_tools import register_render_tools
from openscad_mcp.tools.library_tools import register_library_tools

logger = logging.getLogger(__name__)


@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    client = OpenSCADClient()
    client.ensure_ready()
    logger.info("OpenSCAD MCP server starting — binary: %s", client.binary)
    try:
        yield {"client": client}
    finally:
        logger.info("OpenSCAD MCP server stopped")


mcp = FastMCP("openscad", lifespan=server_lifespan)

register_design_tools(mcp)
register_render_tools(mcp)
register_library_tools(mcp)
