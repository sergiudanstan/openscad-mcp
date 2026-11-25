"""Helpers shared by the tool modules."""

from __future__ import annotations

import functools
import json
from collections.abc import Awaitable, Callable
from typing import Any, NoReturn

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from openscad_mcp import diagnostics
from openscad_mcp.client import OpenSCADClient

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
# Writes output files into the workspace but never deletes user work.
WRITES_OUTPUT = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
OVERWRITES = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)

Params = dict[str, Any] | None


def tool(server, **kwargs: Any) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """Register a tool whose expected failures reach the client with their message.

    MCP SDK 2.x reports any exception other than ToolError only as "Error
    executing tool X", so bad paths, timeouts and invalid values are converted.
    """

    def decorator(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kw: Any) -> Any:
            try:
                return await fn(*args, **kw)
            except ToolError:
                raise
            except (ValueError, OSError, TimeoutError) as exc:
                raise ToolError(json.dumps({"error": str(exc)})) from exc

        server.tool(**kwargs)(wrapper)
        return wrapper

    return decorator


def get_client(ctx: Context) -> OpenSCADClient:
    client: OpenSCADClient = ctx.request_context.lifespan_context["client"]
    if client.binary is None or not client._probed:
        try:
            client.ensure_ready()
        except FileNotFoundError as exc:
            fail(str(exc))
    return client


def fail(message: str, **details: Any) -> NoReturn:
    """Raise a tool error (isError=true) whose text is a JSON object."""
    payload = {"error": message, **{k: v for k, v in details.items() if v not in (None, "", [], {})}}
    raise ToolError(json.dumps(payload))


def console(text: str) -> str:
    return diagnostics.truncate(diagnostics.strip_noise(text).strip())


def diag_summary(text: str) -> dict[str, Any]:
    """Errors/warnings/echo from console text, with empty parts omitted."""
    d = diagnostics.parse_output(text)
    out: dict[str, Any] = {}
    for k in ("errors", "warnings"):
        if d[k]:
            out[k] = d[k][:50]
    if d["echo"]:
        out["echo"] = d["echo"][:100]
    return out
