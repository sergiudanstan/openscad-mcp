"""Entry point: python -m openscad_mcp"""
from openscad_mcp.server import mcp

mcp.run(transport="stdio")
