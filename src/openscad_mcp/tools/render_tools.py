"""Render and export tools for the OpenSCAD MCP server."""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.utilities.types import Image

from openscad_mcp.tools._common import Params, WRITES_OUTPUT, console, diag_summary, fail, get_client, tool

SUPPORTED_EXPORT_FORMATS = {"stl", "3mf", "off", "amf", "dxf", "svg", "pdf", "csg", "png", "echo", "ast"}

# Gimbal rotations [rx, ry, rz] (OpenSCAD --camera tx,ty,tz,rx,ry,rz,dist).
# Distance and centre come from --viewall/--autocenter.
VIEWS = {
    "isometric": (55, 0, 25),
    "front": (90, 0, 0),
    "back": (90, 0, 180),
    "right": (90, 0, 90),
    "left": (90, 0, 270),
    "top": (0, 0, 0),
    "bottom": (180, 0, 0),
    "dimetric": (65, 0, 30),
}
MAX_IMAGE_SIDE = 2048
MAX_FRAMES = 720


def _png_size(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()[:24]
    if len(data) == 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    return None


def register_render_tools(mcp: MCPServer) -> None:
    """Register render and export tools with the MCP server."""

    @tool(mcp, annotations=WRITES_OUTPUT)
    async def openscad_export(
        ctx: Context,
        filename: str,
        output_format: str = "stl",
        output_filename: str | None = None,
        parameters: Params = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Export a .scad file to STL (binary), 3MF, OFF, AMF, DXF, SVG, PDF, CSG, ECHO or AST.

        Args:
            filename: Path to the .scad file (relative to workspace).
            output_format: Output format (file extension).
            output_filename: Output filename. If None, derived from filename with new extension.
            parameters: Variable overrides, typed: {"size": 10, "label": "A", "holes": [1, 2], "solid": true}.
                Strings that are numbers/vectors/booleans pass through as written.
            timeout: Seconds before the render is aborted (default OPENSCAD_MCP_TIMEOUT, 300).
        """
        client = get_client(ctx)
        fmt = output_format.lower().lstrip(".")
        if fmt not in SUPPORTED_EXPORT_FORMATS:
            fail(f"Unsupported format '{fmt}'. Choose from: {', '.join(sorted(SUPPORTED_EXPORT_FORMATS))}")
        if output_filename is None:
            output_filename = str(Path(filename).with_suffix(f".{fmt}"))
        src = client.resolve_path(filename)
        if not src.is_file():
            fail(f"File not found: {filename}")
        try:
            rc, stdout, stderr = await client.export(
                scad_file=filename, output_file=output_filename, parameters=parameters, timeout=timeout
            )
        except ValueError as exc:
            fail(str(exc))
        out = client.resolve_path(output_filename)
        diag = diag_summary(stderr + stdout)
        if rc != 0 or not out.is_file() or diag.get("errors"):
            fail(f"OpenSCAD export failed (rc={rc})", stderr=console(stderr), **diag)
        result: dict[str, Any] = {"path": str(out), "format": fmt, "bytes": out.stat().st_size, **diag}
        if fmt == "stl":
            from openscad_mcp import geometry

            st = geometry.mesh_stats(geometry.read_stl(out))
            result["mesh"] = {k: v for k, v in st.to_dict().items() if k in ("triangles", "bbox", "volume", "watertight", "bodies")}
        return result

    @tool(mcp, annotations=WRITES_OUTPUT, structured_output=False)
    async def openscad_preview(
        ctx: Context,
        filename: str,
        output_filename: str | None = None,
        width: int = 1024,
        height: int = 768,
        camera: str | None = None,
        colorscheme: str | None = None,
        projection: str | None = None,
        views: list[str] | None = None,
        parameters: Params = None,
        render: bool = False,
        show_edges: bool = False,
        show_axes: bool = False,
        return_image: bool = True,
        timeout: float | None = None,
    ) -> list:
        """Render PNG preview(s) and return them as images you can look at.

        One call can render several standard views in parallel:
        views=["isometric","front","top","right"] (also back, left, bottom, dimetric).
        OpenSCAD draws an empty scene and exits 0 when an assert fails or a
        module is unknown, so read the errors/warnings that follow the image.

        Args:
            filename: Path to the .scad file (relative to workspace).
            output_filename: PNG name for a single view (default <stem>_preview.png).
            width, height: Image size in pixels (max 2048 each).
            camera: Explicit camera "tx,ty,tz,rx,ry,rz,dist" or "ex,ey,ez,cx,cy,cz" (single view).
            colorscheme: e.g. "Cornfield", "Metallic", "Tomorrow Night".
            projection: "p" (perspective) or "o" (orthographic).
            views: Standard views to render; ignored when camera is given.
            parameters: Typed variable overrides, as for openscad_export.
            render: Full CGAL/Manifold render instead of the fast OpenCSG preview.
            show_edges, show_axes: Draw mesh edges / axes.
            return_image: Return the PNG data inline (set false to only write files).
        """
        client = get_client(ctx)
        if not client.resolve_path(filename).is_file():
            fail(f"File not found: {filename}")
        width = max(16, min(int(width), MAX_IMAGE_SIDE))
        height = max(16, min(int(height), MAX_IMAGE_SIDE))
        extra: list[str] = []
        if render:
            extra += ["--render"] + client.features.manifold_args
        view_opts = [o for o, on in (("edges", show_edges), ("axes", show_axes)) if on]
        if view_opts:
            extra += ["--view", ",".join(view_opts)]

        stem = str(Path(filename).with_suffix(""))
        jobs: list[tuple[str, str, str | None]] = []  # (label, output, camera)
        if camera or not views:
            jobs.append(("custom" if camera else "default", output_filename or f"{stem}_preview.png", camera))
        else:
            for v in views:
                key = v.lower().strip()
                if key not in VIEWS:
                    fail(f"Unknown view '{v}'. Choose from: {', '.join(VIEWS)}")
                rx, ry, rz = VIEWS[key]
                jobs.append((key, f"{stem}_{key}.png", f"0,0,0,{rx},{ry},{rz},0"))

        async def one(job: tuple[str, str, str | None]):
            label, out_name, cam = job
            rc, stdout, stderr = await client.preview(
                scad_file=filename, output_png=out_name, imgsize=(width, height), camera=cam,
                colorscheme=colorscheme, projection=projection, extra_args=extra,
                parameters=parameters, timeout=timeout,
            )
            return label, out_name, rc, stdout, stderr

        try:
            results = await asyncio.gather(*(one(j) for j in jobs))
        except ValueError as exc:
            fail(str(exc))
        content: list = []
        meta: dict[str, Any] = {"images": []}
        all_text = ""
        for label, out_name, rc, stdout, stderr in results:
            out = client.resolve_path(out_name)
            all_text += stderr + stdout
            if rc != 0 or not out.is_file():
                fail(f"OpenSCAD preview failed (rc={rc}) for view '{label}'", stderr=console(stderr),
                     **diag_summary(stderr + stdout))
            meta["images"].append({"view": label, "path": str(out), "size": _png_size(out)})
            if return_image:
                content.append(Image(path=out))
        meta.update(diag_summary(all_text))
        if meta.get("errors"):
            meta["note"] = "Errors were reported; the image may be empty or incomplete."
        content.append(json.dumps(meta))
        return content

    @tool(mcp, annotations=WRITES_OUTPUT)
    async def openscad_render_animated(
        ctx: Context,
        filename: str,
        num_frames: int = 30,
        output_prefix: str | None = None,
        width: int = 800,
        height: int = 600,
        mp4: bool = True,
        fps: int = 15,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Render animation frames using the $t variable, and join them into an MP4.

        The .scad file should use $t (0.0–1.0) to define animated geometry.
        Frames are written as <prefix>NNNNN.png; with mp4=true and ffmpeg on
        PATH they are also encoded (H.264) to <stem>.mp4.

        Args:
            filename: Path to the .scad file (relative to workspace).
            num_frames: Number of animation frames to render (max 720).
            output_prefix: Prefix for output frame files. If None, derived from filename.
            width, height: Frame size in pixels.
            mp4: Encode the frames to MP4 with ffmpeg when available.
            fps: Frames per second of the MP4.
        """
        client = get_client(ctx)
        if not client.resolve_path(filename).is_file():
            fail(f"File not found: {filename}")
        if not 1 <= num_frames <= MAX_FRAMES:
            fail(f"num_frames must be between 1 and {MAX_FRAMES}.")
        stem = str(Path(filename).with_suffix(""))
        if output_prefix is None:
            output_prefix = f"{stem}_frame.png"
        prefix_path = client.resolve_path(output_prefix)
        frame_stem = prefix_path.with_suffix("").name
        frame_re = re.compile(re.escape(frame_stem) + r"\d+")
        for old in prefix_path.parent.glob(f"{frame_stem}*.png"):
            if frame_re.fullmatch(old.stem):  # only earlier frames of this prefix
                old.unlink()
        rc, stdout, stderr = await client.render_animated(
            scad_file=filename, output_prefix=output_prefix, num_frames=num_frames,
            imgsize=(max(16, min(width, MAX_IMAGE_SIDE)), max(16, min(height, MAX_IMAGE_SIDE))),
            timeout=timeout,
        )
        frames = sorted(
            p for p in prefix_path.parent.glob(f"{frame_stem}*.png")
            if frame_re.fullmatch(p.stem)
        )
        if rc != 0 or not frames:
            fail(f"OpenSCAD animation failed (rc={rc})", stderr=console(stderr), **diag_summary(stderr + stdout))
        result: dict[str, Any] = {
            "output_prefix": output_prefix,
            "num_frames": num_frames,
            "frames_written": len(frames),
            "first_frame": str(frames[0]),
            "last_frame": str(frames[-1]),
            "width": width,
            "height": height,
            **diag_summary(stderr + stdout),
        }
        ffmpeg = shutil.which("ffmpeg")
        if mp4 and ffmpeg:
            digits = len(frames[0].stem) - len(frame_stem)
            video = client.resolve_path(f"{stem}.mp4")
            proc = await asyncio.create_subprocess_exec(
                ffmpeg, "-y", "-loglevel", "error", "-framerate", str(max(1, fps)),
                "-i", str(prefix_path.parent / f"{frame_stem}%0{digits}d.png"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                "-movflags", "+faststart", str(video),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            _, err = await proc.communicate()
            if proc.returncode == 0 and video.is_file():
                result["mp4"] = str(video)
                result["duration_s"] = round(len(frames) / max(1, fps), 3)
            else:
                result["mp4_error"] = err.decode(errors="replace")[-2000:]
        elif mp4:
            result["mp4_error"] = "ffmpeg not found on PATH; frames only."
        return result

    @tool(mcp, annotations=WRITES_OUTPUT)
    async def openscad_get_info(ctx: Context, filename: str) -> dict[str, Any]:
        """Get render statistics (facets, volumes, render time) for a .scad file.

        For exact sizes, volume and mesh health use openscad_measure.
        """
        client = get_client(ctx)
        if not client.resolve_path(filename).is_file():
            fail(f"File not found: {filename}")
        summary_filename = str(Path(filename).with_suffix("")) + "_summary.json"
        client.resolve_path(summary_filename).unlink(missing_ok=True)  # never report a stale summary
        rc, stdout, stderr = await client.get_info(scad_file=filename, summary_file=summary_filename)
        summary_path = client.resolve_path(summary_filename)
        summary_contents = summary_path.read_text(errors="replace") if summary_path.exists() else None
        if rc != 0 and summary_contents is None:
            fail(f"OpenSCAD info failed (rc={rc})", stderr=console(stderr), **diag_summary(stderr + stdout))
        result: dict[str, Any] = {"summary_file": str(summary_path), "backend": client.features.backend}
        if summary_contents:
            try:
                result["summary"] = json.loads(summary_contents)
            except json.JSONDecodeError:
                result["summary_raw"] = summary_contents
        result.update(diag_summary(stderr + stdout))
        if console(stderr):
            result["stderr"] = console(stderr)
        return result
