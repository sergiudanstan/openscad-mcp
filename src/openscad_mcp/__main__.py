"""Entry point: python -m openscad_mcp

Transport is selected by the MCP_TRANSPORT env var:
  - "stdio" (default, local Claude Desktop subprocess)
  - "streamable-http" (remote, listens on 0.0.0.0:$PORT)
  - "sse" (legacy)
"""
import os

from mcp.server.transport_security import TransportSecuritySettings

from openscad_mcp.server import mcp


def _resolve_port() -> int:
    raw = os.environ.get("PORT") or os.environ.get("MCP_PORT") or "8080"
    return int(raw)


def _http_kwargs() -> dict:
    """Bind address plus, when running behind a hosting proxy (HF Spaces, Render,
    Fly, etc.), no DNS-rebinding protection. The MCP SDK's protection only trusts
    the bind address by default and 421s the proxied request."""
    return {
        "host": os.environ.get("MCP_HOST", "0.0.0.0"),
        "port": _resolve_port(),
        "transport_security": TransportSecuritySettings(enable_dns_rebinding_protection=False),
    }


def main() -> None:
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()

    if transport in ("http", "streamable-http", "streamable_http"):
        mcp.run(transport="streamable-http", **_http_kwargs())
    elif transport == "sse":
        mcp.run(transport="sse", **_http_kwargs())
    else:
        mcp.run(transport="stdio")


main()
