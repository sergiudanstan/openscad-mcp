"""Render and export tools for the OpenSCAD MCP server."""

import json
from pathlib import Path

from mcp.server.fastmcp import Context, FastMCP

SUPPORTED_EXPORT_FORMATS = {"stl", "3mf", "off", "amf", "dxf", "svg", "pdf"}


def register_render_tools(mcp: FastMCP) -> None:
    """Register render and export tools with the MCP server."""

    @mcp.tool()
    async def openscad_export(
        ctx: Context,
        filename: str,
        output_format: str = "stl",
        output_filename: str | None = None,
        parameters: dict[str, str] | None = None,
    ) -> str:
        """Export a .scad file to STL, 3MF, OFF, AMF, DXF, SVG, or PDF.

        Args:
            filename: Path to the .scad file (relative to workspace).
            output_format: Output format — one of stl, 3mf, off, amf, dxf, svg, pdf.
            output_filename: Output filename. If None, derived from filename with new extension.
            parameters: Optional dict of OpenSCAD parameters to override (e.g. {"size": "10"}).
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            fmt = output_format.lower().lstrip(".")
            if fmt not in SUPPORTED_EXPORT_FORMATS:
                return json.dumps(
                    {"error": f"Unsupported format '{fmt}'. Choose from: {', '.join(sorted(SUPPORTED_EXPORT_FORMATS))}"}
                )

            if output_filename is None:
                stem = Path(filename).stem
                output_filename = f"{stem}.{fmt}"

            rc, stdout, stderr = await client.export(
                scad_file=filename,
                output_file=output_filename,
                parameters=parameters,
            )

            if rc != 0:
                return json.dumps({"error": f"OpenSCAD export failed (rc={rc})", "stderr": stderr})

            output_path = str(client.resolve_path(output_filename))
            result: dict = {"path": output_path, "format": fmt}
            if stderr.strip():
                result["warnings"] = stderr.strip()
            return json.dumps(result)

        except Exception as exc:
            return json.dumps({"error": str(exc)})

    @mcp.tool()
    async def openscad_preview(
        ctx: Context,
        filename: str,
        output_filename: str | None = None,
        width: int = 1024,
        height: int = 768,
        camera: str | None = None,
        colorscheme: str | None = None,
        projection: str | None = None,
    ) -> str:
        """Render a PNG preview of a .scad file.

        Args:
            filename: Path to the .scad file (relative to workspace).
            output_filename: Output PNG filename. If None, derived from filename.
            width: Image width in pixels.
            height: Image height in pixels.
            camera: Camera position string (e.g. "0,0,0,0,0,0,500").
            colorscheme: Color scheme name (e.g. "Cornfield", "Metallic").
            projection: Projection type — "p" (perspective) or "o" (orthogonal).
        """
        try:
            client = ctx.request_context.lifespan_context["client"]

            if output_filename is None:
                stem = Path(filename).stem
                output_filename = f"{stem}_preview.png"

            rc, stdout, stderr = await client.preview(
                scad_file=filename,
                output_png=output_filename,
                imgsize=(width, height),
                camera=camera,
                colorscheme=colorscheme,
                projection=projection,
            )

            if rc != 0:
                return json.dumps({"error": f"OpenSCAD preview failed (rc={rc})", "stderr": stderr})

            output_path = str(client.resolve_path(output_filename))
            result: dict = {"path": output_path}
            if stderr.strip():
                result["warnings"] = stderr.strip()
            return json.dumps(result)

        except Exception as exc:
            return json.dumps({"error": str(exc)})

    @mcp.tool()
    async def openscad_render_animated(
        ctx: Context,
        filename: str,
        num_frames: int = 30,
        output_prefix: str | None = None,
        width: int = 800,
        height: int = 600,
    ) -> str:
        """Render animation frames using the $t variable.

        The .scad file should use $t (0.0–1.0) to define animated geometry.
        Frames are written as <output_prefix>NNNN.png.

        Args:
            filename: Path to the .scad file (relative to workspace).
            num_frames: Number of animation frames to render.
            output_prefix: Prefix for output frame files. If None, derived from filename.
            width: Frame width in pixels.
            height: Frame height in pixels.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]

            if output_prefix is None:
                stem = Path(filename).stem
                output_prefix = f"{stem}_frame.png"

            rc, stdout, stderr = await client.render_animated(
                scad_file=filename,
                output_prefix=output_prefix,
                num_frames=num_frames,
                imgsize=(width, height),
            )

            if rc != 0:
                return json.dumps({"error": f"OpenSCAD animation failed (rc={rc})", "stderr": stderr})

            result: dict = {
                "output_prefix": output_prefix,
                "num_frames": num_frames,
                "width": width,
                "height": height,
            }
            if stderr.strip():
                result["warnings"] = stderr.strip()
            return json.dumps(result)

        except Exception as exc:
            return json.dumps({"error": str(exc)})

    @mcp.tool()
    async def openscad_get_info(
        ctx: Context,
        filename: str,
    ) -> str:
        """Get render statistics and model info for a .scad file.

        Uses OpenSCAD's --summary-file flag to collect geometry and render stats.

        Args:
            filename: Path to the .scad file (relative to workspace).
        """
        try:
            client = ctx.request_context.lifespan_context["client"]

            stem = Path(filename).stem
            summary_filename = f"{stem}_summary.json"

            rc, stdout, stderr = await client.get_info(
                scad_file=filename,
                summary_file=summary_filename,
            )

            summary_path = client.resolve_path(summary_filename)
            summary_contents: str | None = None
            if summary_path.exists():
                summary_contents = summary_path.read_text(errors="replace")

            if rc != 0 and summary_contents is None:
                return json.dumps({"error": f"OpenSCAD info failed (rc={rc})", "stderr": stderr})

            result: dict = {"summary_file": str(summary_path)}
            if summary_contents:
                try:
                    result["summary"] = json.loads(summary_contents)
                except json.JSONDecodeError:
                    result["summary_raw"] = summary_contents
            if stderr.strip():
                result["stderr"] = stderr.strip()
            return json.dumps(result)

        except Exception as exc:
            return json.dumps({"error": str(exc)})
