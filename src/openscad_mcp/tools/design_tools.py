"""Design tools for creating, reading, and editing OpenSCAD files."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import Context, MCPServer

from openscad_mcp import diagnostics
from openscad_mcp.tools._common import OVERWRITES, READ_ONLY, fail, get_client, tool

MAX_FILE_BYTES = 5 * 1024 * 1024


def _etag(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _atomic_write(path: Path, text: str) -> None:
    if len(text.encode("utf-8")) > MAX_FILE_BYTES:
        fail(f"File too large (limit {MAX_FILE_BYTES // 1024 // 1024} MB).")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def register_design_tools(mcp: MCPServer) -> None:
    """Register design tools with the MCP server."""

    @tool(mcp, annotations=OVERWRITES)
    async def openscad_create(ctx: Context, filename: str, code: str) -> dict[str, Any]:
        """Write a new .scad file with the given OpenSCAD code (overwrites if it exists).

        Paths are relative to the workspace; subfolders are created as needed.
        """
        client = get_client(ctx)
        path = client.resolve_path(filename)
        existed = path.exists()
        _atomic_write(path, code)
        return {
            "path": str(path),
            "message": f"File {'overwritten' if existed else 'created'}: {filename}",
            "etag": _etag(code),
        }

    @tool(mcp, annotations=READ_ONLY)
    async def openscad_read(ctx: Context, filename: str, with_line_numbers: bool = False) -> dict[str, Any]:
        """Read the contents of an existing .scad file.

        Args:
            filename: Path relative to the workspace.
            with_line_numbers: Prefix each line with its number (matches error line numbers).
        """
        client = get_client(ctx)
        path = client.resolve_path(filename)
        if not path.is_file():
            fail(f"File not found: {filename}")
        content = path.read_text(encoding="utf-8", errors="replace")
        shown = content
        if with_line_numbers:
            shown = "\n".join(f"{i:5d}  {ln}" for i, ln in enumerate(content.splitlines(), 1))
        return {"path": str(path), "content": shown, "lines": content.count("\n") + 1, "etag": _etag(content)}

    @tool(mcp, annotations=OVERWRITES)
    async def openscad_edit(
        ctx: Context,
        filename: str,
        code: str | None = None,
        old_string: str | None = None,
        new_string: str | None = None,
        replace_all: bool = False,
        expected_etag: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing .scad file: either replace it whole (`code`) or
        replace an exact snippet (`old_string` -> `new_string`), which is far
        cheaper for small changes. The snippet must occur exactly once unless
        replace_all is true. Pass `expected_etag` (from read/create) to refuse
        the edit if the file changed since you last saw it.
        """
        client = get_client(ctx)
        path = client.resolve_path(filename)
        if not path.is_file():
            fail(f"File not found: {filename}. Use openscad_create to create new files.")
        current = path.read_text(encoding="utf-8")
        if expected_etag and expected_etag != _etag(current):
            fail("File changed since it was read (etag mismatch). Read it again first.",
                 current_etag=_etag(current))
        if code is not None:
            if old_string is not None:
                fail("Pass either code or old_string/new_string, not both.")
            updated, replacements = code, None
        elif old_string is not None and new_string is not None:
            count = current.count(old_string)
            if count == 0:
                fail("old_string not found in file.")
            if count > 1 and not replace_all:
                fail(f"old_string occurs {count} times; add context or set replace_all=true.")
            updated = current.replace(old_string, new_string) if replace_all else current.replace(old_string, new_string, 1)
            replacements = count if replace_all else 1
        else:
            fail("Nothing to do: pass code, or old_string and new_string.")
        _atomic_write(path, updated)
        result: dict[str, Any] = {"path": str(path), "message": f"File updated: {filename}", "etag": _etag(updated)}
        if replacements is not None:
            result["replacements"] = replacements
        return result

    @tool(mcp, annotations=READ_ONLY)
    async def openscad_get_parameters(ctx: Context, filename: str) -> dict[str, Any]:
        """List a model's customizer parameters: top-level literal assignments
        before the first module/function, with `// [min:step:max]` constraints,
        descriptions and `/* [Group] */` headings. Override any of them with the
        `parameters` argument of preview/export/measure tools.
        """
        client = get_client(ctx)
        path = client.resolve_path(filename)
        if not path.is_file():
            fail(f"File not found: {filename}")
        params = diagnostics.extract_parameters(path.read_text(encoding="utf-8", errors="replace"))
        return {"filename": filename, "parameters": params, "count": len(params)}
