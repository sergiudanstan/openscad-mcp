"""Exact geometry analysis: measure, mass, interference, sections, printability.

Every tool renders the model to a cached binary STL first (re-rendered only
when the file or anything it includes changes) and analyses that mesh, so
repeated questions about the same model cost milliseconds, not renders.
"""

from __future__ import annotations

import asyncio
import json
import secrets
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.utilities.types import Image

from openscad_mcp import diagnostics, geometry
from openscad_mcp.client import RENDER_TIMEOUT, MeshResult, OpenSCADClient
from openscad_mcp.tools._common import (
    Params, READ_ONLY, WRITES_OUTPUT, compact_diag, fail, failure_info, get_client, tool,
)

# CGAL refuses to import open or non-manifold meshes (and aborts on some
# self-intersecting ones); the intersection is then estimated without CGAL.
_CGAL_IMPORT_FAILED = ("not closed", "Unable to convert", "CGAL error")


def _scad_str(path: Path) -> str:
    return json.dumps(str(path))


async def _mesh(client: OpenSCADClient, filename: str, parameters: Params, timeout: float | None,
                use_cache: bool = True) -> MeshResult:
    src = client.resolve_path(filename)
    if not src.is_file():
        fail(f"File not found: {filename}")
    try:
        res = await client.render_mesh(src, parameters=parameters, timeout=timeout, use_cache=use_cache)
    except ValueError as exc:
        fail(str(exc))
    return res


def _diag(res: MeshResult) -> dict[str, Any]:
    return compact_diag(res.diagnostics)


async def _measure_2d(client: OpenSCADClient, filename: str, parameters: Params, timeout: float | None) -> dict:
    src = client.resolve_path(filename)
    svg = client.scratch_dir() / f"m2d_{secrets.token_hex(8)}.svg"
    try:
        rc, stdout, stderr = await client.run(
            ["-o", str(svg), *diagnostics.define_args(parameters), str(src)], timeout=timeout
        )
        if rc != 0 or not svg.is_file():
            fail("2D export for measurement failed", **failure_info(stderr + stdout))
        stats = geometry.contours_stats(geometry.read_svg_contours(svg))
    finally:
        svg.unlink(missing_ok=True)
    return {"dimension": 2, **stats}


def _require(res: MeshResult, what: str) -> Path:
    if not res.ok or res.stl is None:
        fail(f"Render for {what} failed (rc={res.returncode})", **failure_info(res.output, res.diagnostics))
    return res.stl


def _sampled_overlap(sa: Path, sb: Path, ta: geometry.MeshStats, tb: geometry.MeshStats, why: str) -> dict:
    """Overlap by ray sampling, refined until the error bound is within 5 %."""
    tris_a, tris_b = geometry.read_stl(sa), geometry.read_stl(sb)
    for n in (64, 128, 256):
        est = geometry.ray_overlap(tris_a, tris_b, (ta.bbox_min, ta.bbox_max), (tb.bbox_min, tb.bbox_max), n=n)
        if est["volume"] == 0 or est["error_bound"] <= 0.05 * est["volume"]:
            break
    vol = est["volume"]
    out: dict[str, Any] = {
        "status": est["status"],
        "interference_volume": round(vol, 4),
        "method": "ray_sampled",
        "resolution_mm": [round(h, 6) for h in est["cell"]],
        "volume_error_bound": round(est["error_bound"], 4),
    }
    if est["status"] == "interference":
        lo, hi = est["bbox_min"], est["bbox_max"]
        out["interference_bbox"] = {"min": [round(v, 6) for v in lo], "max": [round(v, 6) for v in hi],
                                    "size": [round(hi[i] - lo[i], 6) for i in range(3)]}
        out["interference_centroid"] = [round(v, 6) for v in est["centroid"]]
        out["fraction_of_a"] = round(vol / abs(ta.volume), 6) if ta.volume else None
        out["fraction_of_b"] = round(vol / abs(tb.volume), 6) if tb.volume else None
    if est["invalid_rays"]:
        out["invalid_rays"] = est["invalid_rays"]
        out["volume_is_lower_bound"] = True
    note = f"{why}; overlap estimated by ray sampling."
    if est["status"] == "touching_or_near":
        note += f" Overlaps thinner than about {max(est['cell']):.3g} mm can be missed."
    out["note"] = note
    return out


def _section_scad(loops: list[list[tuple[float, float]]]) -> str:
    """OpenSCAD code drawing the cut face: one polygon path per loop (OpenSCAD
    fills multiple paths even-odd, so holes and islands come out right). The
    loops are already in plane coordinates, so the top view shows the cut."""
    points: list[str] = []
    paths: list[str] = []
    for loop in loops:
        start = len(points)
        points += [f"[{u:.9g},{v:.9g}]" for u, v in loop]
        paths.append("[" + ",".join(str(i) for i in range(start, len(points))) + "]")
    return f'color("SteelBlue") polygon(points=[{",".join(points)}], paths=[{",".join(paths)}]);\n'


def register_analysis_tools(mcp: MCPServer) -> None:
    """Register measurement and engineering-analysis tools."""

    @tool(mcp, annotations=READ_ONLY)
    async def openscad_measure(
        ctx: Context,
        filename: str,
        parameters: Params = None,
        timeout: float | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Exact numbers from the rendered geometry (mm): bounding box (min, max,
        size, center), volume, surface area, centroid, watertightness, number of
        separate bodies, triangle/vertex counts and mesh-health edge counts.
        2D models return area, perimeter, contour count and 2D bbox.
        Prefer this over judging a picture.
        """
        client = get_client(ctx)
        res = await _mesh(client, filename, parameters, timeout, use_cache)
        if not res.ok and res.dimension == 2:
            return {"filename": filename, **await _measure_2d(client, filename, parameters, timeout)}
        stl = _require(res, "measurement")
        stats = geometry.mesh_stats(geometry.read_stl(stl))
        if stats.triangles == 0:
            fail("Model rendered to an empty mesh.", **_diag(res))
        return {"filename": filename, "dimension": 3, **stats.to_dict(), "cached": res.cached,
                "backend": client.features.backend, **_diag(res)}

    @tool(mcp, annotations=READ_ONLY)
    async def openscad_mass_properties(
        ctx: Context,
        filename: str,
        material: str = "pla",
        density_g_cm3: float | None = None,
        infill_fraction: float = 1.0,
        parameters: Params = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Mass, centre of mass and inertia tensor (about the COM) of a solid model.

        Args:
            material: pla, petg, abs, asa, tpu, nylon, pc, resin, aluminium, steel,
                stainless, brass, copper, titanium, wood (ignored if density given).
            density_g_cm3: Explicit density in g/cm^3.
            infill_fraction: Scale the density for partly-filled prints (0-1]; a
                rough estimate, since shells are denser than infill.
        Units: mass g, lengths mm, inertia g*mm^2 (divide by 1e9 for kg*m^2).
        """
        client = get_client(ctx)
        if density_g_cm3 is None:
            density_g_cm3 = geometry.MATERIAL_DENSITY.get(material.lower())
            if density_g_cm3 is None:
                fail(f"Unknown material '{material}'.", known=sorted(geometry.MATERIAL_DENSITY))
        if not 0 < infill_fraction <= 1:
            fail("infill_fraction must be in (0, 1].")
        res = await _mesh(client, filename, parameters, timeout)
        stl = _require(res, "mass properties")
        tris = geometry.read_stl(stl)
        st = geometry.mesh_stats(tris)
        props = geometry.mass_properties(tris, density_g_cm3 * infill_fraction)
        if "error" in props:
            fail(props["error"])
        out = {"filename": filename, "material": None if material is None else material.lower(), **props,
               "watertight": st.watertight, "bodies": st.bodies, **_diag(res)}
        if not st.watertight:
            out["warning"] = "Mesh is not watertight; volume-based values are unreliable."
        return out

    @tool(mcp, annotations=READ_ONLY)
    async def openscad_interference(
        ctx: Context,
        file_a: str,
        file_b: str,
        parameters_a: Params = None,
        parameters_b: Params = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Check whether two parts overlap. Both are rendered (cached) in their
        own coordinates; OpenSCAD intersects the meshes and the overlap volume,
        bbox and centroid are reported. status: "clear" (bboxes apart),
        "touching_or_near" (bboxes overlap, solids do not), or "interference".
        When CGAL cannot intersect them (a part is non-manifold, or it timed
        out), the overlap is estimated by ray sampling instead: method
        "ray_sampled" with resolution_mm and volume_error_bound, and status
        "indeterminate" if an open mesh leaves the answer unknown.
        """
        client = get_client(ctx)
        ra, rb = await asyncio.gather(
            _mesh(client, file_a, parameters_a, timeout), _mesh(client, file_b, parameters_b, timeout)
        )
        sa, sb = _require(ra, file_a), _require(rb, file_b)
        ta, tb = geometry.mesh_stats(geometry.read_stl(sa)), geometry.mesh_stats(geometry.read_stl(sb))
        overlap = [min(ta.bbox_max[i], tb.bbox_max[i]) - max(ta.bbox_min[i], tb.bbox_min[i]) for i in range(3)]
        base = {
            "a": {"file": file_a, "volume": round(ta.volume, 4), "watertight": ta.watertight},
            "b": {"file": file_b, "volume": round(tb.volume, 4), "watertight": tb.watertight},
            "bbox_overlap": [round(v, 6) for v in overlap],
        }
        if min(overlap) < 0:
            gap = max(-v for v in overlap)
            return {**base, "status": "clear", "interference_volume": 0.0, "min_bbox_gap": round(gap, 6)}
        wrapper = client.write_wrapper(
            f"intersection() {{ import({_scad_str(sa)}, convexity=10); import({_scad_str(sb)}, convexity=10); }}\n"
        )
        try:
            res = await client.render_mesh(wrapper, timeout=timeout)
        except TimeoutError:
            return {**base, **_sampled_overlap(sa, sb, ta, tb,
                                               f"CGAL timed out after {timeout or RENDER_TIMEOUT:g} s")}
        if not res.ok:
            if any(m in res.output for m in _CGAL_IMPORT_FAILED):
                return {**base, **_sampled_overlap(sa, sb, ta, tb, "CGAL could not intersect the meshes "
                                                   "(open or non-manifold; see openscad_measure mesh_health)")}
            if "Current top level object is empty" in res.output and not res.diagnostics.get("errors"):
                return {**base, "status": "touching_or_near", "interference_volume": 0.0}
            fail("Intersection render failed", **failure_info(res.output, res.diagnostics))
        st = geometry.mesh_stats(geometry.read_stl(res.stl))  # type: ignore[arg-type]
        vol = abs(st.volume)
        if st.triangles == 0 or vol < 1e-6:
            return {**base, "status": "touching_or_near", "interference_volume": round(vol, 6)}
        d = st.to_dict()
        return {**base, "status": "interference", "interference_volume": round(vol, 4),
                "interference_bbox": d["bbox"], "interference_centroid": d["centroid"],
                "fraction_of_a": round(vol / abs(ta.volume), 6) if ta.volume else None,
                "fraction_of_b": round(vol / abs(tb.volume), 6) if tb.volume else None}

    @tool(mcp, annotations=WRITES_OUTPUT, structured_output=False)
    async def openscad_section(
        ctx: Context,
        filename: str,
        axis: str = "z",
        offset: float = 0.0,
        parameters: Params = None,
        return_image: bool = True,
        width: int = 800,
        height: int = 600,
        timeout: float | None = None,
    ) -> list:
        """Cut the model with the plane axis=offset (mm) and report the section:
        area, bounding box (in the cut plane) and an image of the cut face.
        Use it to check wall thickness, bores and internal cavities.
        Plane coordinates: z-cut -> (x, y); y-cut -> (x, -z); x-cut -> (-z, y).
        """
        client = get_client(ctx)
        axis = axis.lower()
        if axis not in ("x", "y", "z"):
            fail("axis must be x, y or z.")
        res = await _mesh(client, filename, parameters, timeout)
        stl = _require(res, "section")
        # Sliced in Python from the cached mesh: no second CGAL render, and a
        # non-manifold mesh (which CGAL refuses to re-import) still gets a section.
        cut = geometry.section(geometry.read_stl(stl), axis, offset)
        meta: dict[str, Any] = {"filename": filename, "axis": axis, "offset": offset}
        if cut is None:
            meta.update({"area": 0.0, "note": "The plane does not cut the model."})
            return [json.dumps(meta)]
        meta.update({"area": round(cut["area"], 4), "bbox_2d": cut["bbox_2d"], "regions": cut["regions"]})
        if cut["open_chains"]:
            meta["warning"] = ("The cut crosses open or non-manifold parts of the mesh (see openscad_measure "
                               "mesh_health); area and regions are approximate.")
        if cut["on_face"]:
            meta["note"] = ("The plane lies on a face of the model: the section is taken just below it (just "
                            "above where nothing is below). Offset it by 0.01 mm to choose a side.")
        content: list = []
        if return_image:
            png_name = f"{Path(filename).with_suffix('')}_section_{axis}{offset:g}.png"
            img_src = client.write_wrapper(_section_scad(cut["loops"]))
            rc, stdout, stderr = await client.preview(
                scad_file=filename, output_png=png_name, imgsize=(width, height),
                camera="0,0,0,0,0,0,0", projection="o", src_path=img_src, timeout=timeout,
            )
            out = client.resolve_path(png_name)
            if rc == 0 and out.is_file():
                meta["image"] = str(out)
                content.append(Image(path=out))
        content.append(json.dumps(meta))
        return content

    @tool(mcp, annotations=READ_ONLY)
    async def openscad_print_report(
        ctx: Context,
        filename: str,
        overhang_deg: float = 45.0,
        build_volume: list[float] | None = None,
        parameters: Params = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """FDM printability digest for the model as oriented (Z up, bed at min Z):
        overhang area beyond overhang_deg from vertical, bed contact area,
        fit in build_volume [x, y, z] mm (default 256^3), watertightness,
        separate bodies, and a list of issues.
        """
        client = get_client(ctx)
        bv = tuple(build_volume or (256.0, 256.0, 256.0))
        if len(bv) != 3:
            fail("build_volume must be [x, y, z].")
        res = await _mesh(client, filename, parameters, timeout)
        stl = _require(res, "print report")
        report = geometry.print_report(geometry.read_stl(stl), overhang_deg, bv)  # type: ignore[arg-type]
        if "error" in report:
            fail(report["error"])
        return {"filename": filename, **report, **_diag(res)}

    @tool(mcp, annotations=READ_ONLY)
    async def openscad_eval(
        ctx: Context,
        expressions: list[str],
        filename: str | None = None,
        parameters: Params = None,
    ) -> dict[str, Any]:
        """Evaluate OpenSCAD expressions, optionally in a model's scope (its
        variables and functions), without building geometry. Example:
        expressions=["wall*2 + clearance", "len(holes)"], filename="box.scad".
        Values come back as OpenSCAD prints them (6 significant digits).
        """
        client = get_client(ctx)
        if not expressions:
            fail("Pass at least one expression.")
        try:
            results, text = await client.evaluate(filename, expressions, parameters)
        except ValueError as exc:
            fail(str(exc))
        from openscad_mcp import diagnostics

        d = diagnostics.parse_output(text)
        out: dict[str, Any] = {"results": results}
        if d["errors"]:
            out["errors"] = d["errors"][:50]
        if d["warnings"]:
            out["warnings"] = d["warnings"][:50]
        return out
