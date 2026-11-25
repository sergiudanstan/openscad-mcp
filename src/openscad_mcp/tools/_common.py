"""Helpers shared by the tool modules."""

from __future__ import annotations

import asyncio
import functools
import json
import re
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


async def get_client(ctx: Context) -> OpenSCADClient:
    client: OpenSCADClient = ctx.request_context.lifespan_context["client"]
    if client.binary is None or not client._probed:
        try:
            # In a thread: the startup probe may still hold the lock, and a slow
            # binary must not freeze the event loop (other calls, SIGTERM).
            await asyncio.to_thread(client.ensure_ready)
        except OSError as exc:  # missing binary, or a workspace that cannot be created
            fail(str(exc))
    return client


def fail(message: str, **details: Any) -> NoReturn:
    """Raise a tool error (isError=true) whose text is a JSON object."""
    payload = {"error": message, **{k: v for k, v in details.items() if v not in (None, "", [], {})}}
    raise ToolError(json.dumps(payload))


def console(text: str) -> str:
    return diagnostics.truncate(diagnostics.strip_noise(text).strip())


_LOC_TAIL = re.compile(r',?\s*in file "?[^,"]+?"?, line \d+\s*$')
MAX_ITEMS = 50
MAX_NOTES = 20
MAX_LINES_PER_ITEM = 50
ECHO_LINES = 10


def _grouped(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The location moves from the message text into file/line, and repeats of
    one message in one file merge into a single entry: `lines` lists each line
    once, and `count` gives the number of occurrences when a line repeats."""
    out: list[dict[str, Any]] = []
    groups: dict[tuple[str, Any], tuple[dict[str, Any], list[int], list[int]]] = {}
    for item in items:
        if "line" not in item:
            out.append(item)
            continue
        entry = {**item, "message": _LOC_TAIL.sub("", item["message"])}
        if "trace" in entry:  # a call stack belongs to one occurrence
            out.append(entry)
            continue
        key = (entry["message"], entry.get("file"))
        group = groups.get(key)
        if group is None:
            groups[key] = (entry, [entry["line"]], [1])
            out.append(entry)
        else:
            group[2][0] += 1
            if entry["line"] not in group[1]:
                group[1].append(entry["line"])
    for entry, lines, count in groups.values():
        if len(lines) > 1:
            del entry["line"]
            entry["lines"] = lines[:MAX_LINES_PER_ITEM]
        if count[0] > len(lines) or len(lines) > MAX_LINES_PER_ITEM:
            entry["count"] = count[0]
    return out


def compact_diag(d: dict[str, Any], echo_lines: int = ECHO_LINES, max_items: int = MAX_ITEMS) -> dict[str, Any]:
    """What OpenSCAD reported, compactly: errors and warnings with repeats
    merged, at most `echo_lines` echo lines (the first and the last half, which
    is where a failure is), and any other console lines (DEPRECATED,
    EXPORT-WARNING, crash text) once each as `notes`. Counts of anything left
    out are given; empty parts are omitted."""
    out: dict[str, Any] = {}
    for k in ("errors", "warnings"):
        items = _grouped(d.get(k) or [])
        if items:
            out[k] = items[:max_items]
            if len(items) > max_items:
                out[f"{k}_omitted"] = len(items) - max_items
    echo = d.get("echo") or []
    if len(echo) > echo_lines:
        head = (echo_lines + 1) // 2
        tail = echo_lines - head
        omitted = len(echo) - echo_lines
        out["echo"] = [*echo[:head], f"... {omitted} echo lines omitted ...", *(echo[-tail:] if tail else [])]
        out["echo_omitted"] = omitted
    elif echo:
        out["echo"] = echo
    notes = list(dict.fromkeys(d.get("other") or []))
    if notes:
        out["notes"] = notes[:MAX_NOTES]
        if len(notes) > MAX_NOTES:
            out["notes_omitted"] = len(notes) - MAX_NOTES
    return out


def diag_summary(text: str) -> dict[str, Any]:
    """compact_diag of raw console text."""
    return compact_diag(diagnostics.parse_output(text))


def failure_info(text: str, d: dict[str, Any] | None = None) -> dict[str, Any]:
    """Details for a failed run: the parsed diagnostics, plus the raw console
    only when nothing in it could be parsed."""
    info = compact_diag(d if d is not None else diagnostics.parse_output(text))
    if not info:
        raw = console(text)
        if raw:
            info["console"] = raw[:2000]
    return info
