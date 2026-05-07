"""Entry point: python -m openscad_mcp

Transport is selected by the MCP_TRANSPORT env var:
  - "stdio" (default, local Claude Desktop subprocess)
  - "streamable-http" (remote, listens on 0.0.0.0:$PORT)
  - "sse" (legacy)
"""
import os

from openscad_mcp.server import mcp


def _resolve_port() -> int:
    raw = os.environ.get("PORT") or os.environ.get("MCP_PORT") or "8080"
    return int(raw)


def _relax_host_validation() -> None:
    """Allow any Host/Origin header when running behind a hosting proxy
    (HF Spaces, Render, Fly, etc.). The MCP SDK's DNS-rebinding protection
    only trusts the bind address by default and 421s the proxied request."""
    try:
        sec = mcp.settings.transport_security
        sec.enable_dns_rebinding_protection = False
        sec.allowed_hosts = ["*"]
        sec.allowed_origins = ["*"]
    except Exception:
        pass


def main() -> None:
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()

    if transport in ("http", "streamable-http", "streamable_http"):
        mcp.settings.host = os.environ.get("MCP_HOST", "0.0.0.0")
        mcp.settings.port = _resolve_port()
        _relax_host_validation()
        mcp.run(transport="streamable-http")
    elif transport == "sse":
        mcp.settings.host = os.environ.get("MCP_HOST", "0.0.0.0")
        mcp.settings.port = _resolve_port()
        _relax_host_validation()
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")


main()
