"""Design tools for creating, reading, and editing OpenSCAD files."""

import json

from mcp.server.fastmcp import FastMCP, Context


def register_design_tools(mcp: FastMCP) -> None:
    """Register design tools with the MCP server."""

    @mcp.tool()
    async def openscad_create(ctx: Context, filename: str, code: str) -> str:
        """Write a new .scad file with the given OpenSCAD code."""
        try:
            client = ctx.request_context.lifespan_context["client"]
            path = client.resolve_path(filename)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(code, encoding="utf-8")
            return json.dumps({"path": str(path), "message": f"File created: {filename}"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def openscad_read(ctx: Context, filename: str) -> str:
        """Read the contents of an existing .scad file."""
        try:
            client = ctx.request_context.lifespan_context["client"]
            path = client.resolve_path(filename)
            if not path.exists():
                return json.dumps({"error": f"File not found: {filename}"})
            content = path.read_text(encoding="utf-8")
            return json.dumps({"path": str(path), "content": content})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def openscad_edit(ctx: Context, filename: str, code: str) -> str:
        """Overwrite/update an existing .scad file with new OpenSCAD code."""
        try:
            client = ctx.request_context.lifespan_context["client"]
            path = client.resolve_path(filename)
            if not path.exists():
                return json.dumps({"error": f"File not found: {filename}. Use openscad_create to create new files."})
            path.write_text(code, encoding="utf-8")
            return json.dumps({"path": str(path), "message": f"File updated: {filename}"})
        except Exception as e:
            return json.dumps({"error": str(e)})
