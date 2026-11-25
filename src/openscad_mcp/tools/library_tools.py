"""Library tools: listing files, cheatsheet, version, syntax check, examples, library management."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import Context, MCPServer

from openscad_mcp import diagnostics
from openscad_mcp.tools._common import (
    OVERWRITES, Params, READ_ONLY, WRITES_OUTPUT, compact_diag, fail, get_client, tool,
)

# Examples ship inside the package so they exist in wheel installs too.
_EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
# Larger examples are copied to the workspace but not inlined (the biggest is ~28k tokens).
INLINE_EXAMPLE_CHARS = 4000

# Library descriptions for all 25 official OpenSCAD libraries + MCAD
_LIBRARY_INFO = {
    "MCAD": "Built-in library with gears, motors, shapes, materials, math, and more",
    "BOSL2": "Belfry OpenScad Library v2: advanced shapes, rounding, beziers, attachments, distributors",
    "BOSL": "Original Belfry OpenScad Library: tools, shapes, and helpers",
    "dotSCAD": "Math-driven 3D modeling: Voronoi, path extrusion, maze, polyhedra, turtle graphics",
    "NopSCADlib": "Vitamins library: screws, nuts, PCBs, motors, bearings, electronics, 3D printer parts",
    "UB.scad": "3D printing workflow: object tools, view helpers, mechanical parts",
    "FunctionalOpenSCAD": "Meta-programming: implementing OpenSCAD in OpenSCAD",
    "constructive": "Stamping approach for complex mechanical parts assembly",
    "StoneAgeLib": "Collection of 3D printing model scripts and utilities",
    "BOLTS": "Open Library of Technical Specifications: standard fasteners and hardware",
    "OpenSCAD-Snippet": "Asset collection: mechanical parts, furniture, animation base meshes",
    "BoardGameToolkit": "Board game boxes with tessellation layouts and custom shapes",
    "Round-Anything": "Robust rounding utilities using polyRound approach",
    "MarksEnclosureHelper": "Hinged boxes with rounded corners and various closures",
    "funcutils": "Functional programming techniques for OpenSCAD",
    "threads-scad": "Efficient threading: metric internal/external threads, nuts, bolts",
    "smooth-prim": "Smooth primitives with specified rounded edges",
    "plot-function": "Render math functions in Cartesian, polar, and axial coordinates",
    "closepoints": "Create shapes from point lists using polyhedron transformations",
    "openscad-tray": "Parametric trays with optional subdivisions for storage",
    "YAPP_Box": "Yet Another Parametric Projectbox generator for electronics",
    "STEMFIE": "Educational construction-set parts (STEMFIE project)",
    "catchnhole": "Ergonomic nutcatches, screw holes, and countersinks",
    "pathbuilder": "Complex 2D shapes with fillets/chamfers using SVG-like syntax",
    "SCON": "JSON-like configuration data format for OpenSCAD",
    "A2D": "Altair 2D library: functions, modules, constants for 2D drawing",
}

_CHEATSHEET = """\
OpenSCAD Quick Reference (v2021.01)
====================================

## Syntax
  var = value;
  var = cond ? val_true : val_false;    // ternary
  var = function(x) x + x;             // function literal
  include <file.scad>                   // include file contents
  use <file.scad>                       // import modules/functions only

## Constants
  undef, PI

## Operators
  Arithmetic:  + - * / % ^
  Relational:  < <= == != >= >
  Logical:     && || !

## Modifier Characters
  *  disable       (ignore subtree)
  !  show only     (root and this only)
  #  highlight     (debug — transparent red)
  %  transparent   (background)

## 3D Primitives
  cube(size, center)                         // or cube([w, d, h], center)
  sphere(r | d=diameter)
  cylinder(h, r|d, center)                   // or cylinder(h, r1|d1, r2|d2, center)
  polyhedron(points, faces, convexity)
  import("file.stl|.off|.amf|.3mf", convexity)
  surface(file="file.dat|.png", center, convexity)

## 2D Primitives
  circle(r | d=diameter)
  square(size, center)                       // or square([w, h], center)
  polygon(points, paths)
  text(t, size, font, halign, valign, spacing, direction, language, script)
  import("file.dxf|.svg", convexity)
  projection(cut)                            // project 3D to 2D

## Extrusion (2D → 3D)
  linear_extrude(height, center, convexity, twist, slices, scale) { ... }
  rotate_extrude(angle, convexity) { ... }

## Transforms
  translate([x, y, z])
  rotate([x, y, z])                         // or rotate(a, [x, y, z])
  scale([x, y, z])
  resize([x, y, z], auto, convexity)
  mirror([x, y, z])
  multmatrix(m)                              // 4x4 affine matrix
  color("name", alpha)                       // or color([r,g,b,a]) or color("#hex")
  offset(r|delta, chamfer)                   // 2D inset/outset
  hull()                                     // convex hull
  minkowski(convexity)                       // Minkowski sum

## Boolean Operations
  union()        { ... }
  difference()   { base(); subtracted(); ... }
  intersection() { ... }

## Modules & Functions
  module name(param=default) { ... }
  function name(x) = expression;
  children()                                 // all children of module
  children(idx)                              // specific child by index

## Flow Control
  for (i = [start:end]) { ... }
  for (i = [start:step:end]) { ... }
  for (i = [a, b, c]) { ... }
  for (i = ..., j = ...) { ... }             // nested iteration
  intersection_for(i = ...) { ... }          // intersect loop iterations
  if (cond) { ... } else { ... }
  let (x = expr) { ... }

## List Comprehensions
  [for (i = range|list) expr]                // generate
  [for (i = ...) if (cond) expr]             // filter
  [for (i = ...) if (cond) x else y]         // conditional
  [for (i = ...) let (a = expr) a]           // with assignments
  [each list]                                // flatten

## Lists
  list = [a, b, c];
  list[idx]                                  // zero-based index
  list.x  list.y  list.z                     // dot notation for vectors

## Special Variables
  $fn       — number of fragments (overrides $fa/$fs)
  $fa       — minimum angle per fragment (default 12)
  $fs       — minimum size per fragment (default 2)
  $t        — animation step [0, 1)
  $vpr      — viewport rotation [rx, ry, rz]
  $vpt      — viewport translation [tx, ty, tz]
  $vpd      — viewport camera distance
  $vpf      — viewport field of view
  $children — number of child modules
  $preview  — true in preview (F5), false in render (F6)

## Math Functions
  abs(x), sign(x)
  sin(deg), cos(deg), tan(deg)               // degrees, not radians
  asin(x), acos(x), atan(x), atan2(y, x)
  floor(x), round(x), ceil(x)
  min(a,b,...), max(a,b,...)
  pow(base, exp), sqrt(x), exp(x)
  ln(x), log(x)                              // ln=natural, log=log10
  norm(v), cross(v1, v2)
  rands(min, max, count, seed)

## Type Tests
  is_undef(x), is_bool(x), is_num(x)
  is_string(x), is_list(x), is_function(x)

## String Functions
  str(a, b, ...)                             // concatenate to string
  chr(code)                                  // code → character
  ord(char)                                  // character → code

## Other Functions
  len(list|string)                           // length
  concat(list1, list2, ...)                  // join lists
  lookup(key, [[k,v], ...])                  // lookup table
  search(needle, haystack)                   // search in list/string
  echo(...)                                  // debug output
  assert(cond, msg)                          // assertion

## Other Modules
  render(convexity)                          // force CGAL render
  version()                                  // OpenSCAD version [y,m,d]
  version_num()                              // version as number
  parent_module(idx)                         // name of parent module
"""



_SKIP_DIRS = {".git", ".cache", "__pycache__", "node_modules", ".venv"}


def _workspace_scad_files(root: Path) -> list[Path]:
    """.scad files under root, not following symlinks (libraries are symlinked in)."""
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [
            d for d in dirnames
            if d not in _SKIP_DIRS and not d.startswith(".") and not os.path.islink(os.path.join(dirpath, d))
        ]
        out.extend(Path(dirpath) / f for f in filenames if f.endswith(".scad"))
    return sorted(out)


def _library_entry(lib_dir: Path) -> dict[str, Any]:
    name = lib_dir.name
    scad_files = list(lib_dir.rglob("*.scad"))
    main_files = sorted(
        (f for f in scad_files if f.stem.lower() in (name.lower(), "main", "std", "core", "lib", "all")),
        key=lambda f: len(f.relative_to(lib_dir).parts),
    )
    entry = main_files[0].relative_to(lib_dir) if main_files else None
    return {
        "name": name,
        "description": _LIBRARY_INFO.get(name, "Community library"),
        "scad_files": len(scad_files),
        "entry_point": str(entry) if entry else None,
        "use_example": f"include <{name}/{entry}>" if entry else f"use <{name}/...>",
        "path": str(lib_dir),
    }


def register_library_tools(mcp: MCPServer) -> None:
    """Register library / utility tools with the MCP server."""

    @tool(mcp, annotations=READ_ONLY)
    async def openscad_list_files(ctx: Context, pattern: str | None = None) -> dict[str, Any]:
        """List .scad files in the workspace (relative paths, size, modified time).

        Symlinked library folders are skipped. `pattern` filters by substring.
        """
        client = get_client(ctx)
        root = client.workspace.resolve()
        files = []
        for p in _workspace_scad_files(root):
            rel = str(p.relative_to(root))
            if pattern and pattern.lower() not in rel.lower():
                continue
            st = p.stat()
            files.append({"path": rel, "bytes": st.st_size, "modified": int(st.st_mtime)})
        return {"files": [f["path"] for f in files], "details": files, "count": len(files), "workspace": str(root)}

    @tool(mcp, annotations=READ_ONLY)
    async def openscad_cheatsheet(ctx: Context) -> str:
        """Return an OpenSCAD language quick reference / cheatsheet."""
        return _CHEATSHEET

    @tool(mcp, annotations=READ_ONLY)
    async def openscad_version(ctx: Context) -> dict[str, Any]:
        """Get the installed OpenSCAD version, binary, geometry backend and paths."""
        client = get_client(ctx)
        version_text = await client.version()
        return {
            "version": version_text,
            "binary": client.binary,
            "backend": client.features.backend,
            "summary_file_support": client.features.summary_file,
            "workspace": str(client.workspace),
            "library_paths": client.library_paths(),
            "cache_dir": str(client.cache_dir),
        }

    @tool(mcp, annotations=READ_ONLY)
    async def openscad_check_syntax(ctx: Context, filename: str, parameters: Params = None) -> dict[str, Any]:
        """Parse and evaluate a .scad file without building geometry (fast).

        `passed` is false whenever OpenSCAD reports an ERROR (parse errors,
        failed asserts), whatever its exit code; `strict_passed` additionally
        requires no warnings (unknown modules/variables are only warnings).
        Each error/warning carries file and line (`lines` when one message
        repeats); other console output such as DEPRECATED comes as `notes`.
        """
        client = get_client(ctx)
        if not client.resolve_path(filename).is_file():
            fail(f"File not found: {filename}")
        try:
            rc, stdout, stderr = await client.check_syntax(filename, parameters)
        except ValueError as exc:
            fail(str(exc))
        d = diagnostics.parse_output(stderr + stdout)
        passed = rc == 0 and not d["errors"]
        return {
            "filename": filename,
            "passed": passed,
            "strict_passed": passed and not d["warnings"],
            "returncode": rc,
            "errors": [],
            "warnings": [],
            **compact_diag(d, echo_lines=200, max_items=100),
        }

    @tool(mcp, annotations=READ_ONLY)
    async def openscad_list_examples(ctx: Context) -> dict[str, Any]:
        """List built-in example .scad files shipped with the server."""
        if not _EXAMPLES_DIR.exists():
            return {"examples": [], "note": "examples directory not found"}
        examples = sorted(p.name for p in _EXAMPLES_DIR.glob("*.scad"))
        return {"examples": examples, "count": len(examples), "directory": str(_EXAMPLES_DIR)}

    @tool(mcp, annotations=WRITES_OUTPUT)
    async def openscad_get_example(
        ctx: Context, name: str, copy_to_workspace: bool = True, include_content: bool | None = None
    ) -> dict[str, Any]:
        """Copy a built-in example into the workspace (examples/<name>) so the
        render tools can use it, and return its source. Sources over 4000
        characters are not inlined when copied (read them with openscad_read);
        include_content=true forces the source, false omits it."""
        client = get_client(ctx)
        fname = name if name.endswith(".scad") else f"{name}.scad"
        src = (_EXAMPLES_DIR / fname).resolve()
        if src.parent != _EXAMPLES_DIR.resolve() or not src.is_file():
            fail(f"Example not found: {name}", available=sorted(p.name for p in _EXAMPLES_DIR.glob("*.scad")))
        code = src.read_text(encoding="utf-8")
        result: dict[str, Any] = {"name": fname, "bytes": len(code.encode("utf-8")), "lines": code.count("\n") + 1}
        inline = include_content if include_content is not None else (
            not copy_to_workspace or len(code) <= INLINE_EXAMPLE_CHARS)
        if inline:
            result["content"] = code
        if copy_to_workspace:
            dst = client.resolve_path(f"examples/{fname}")
            result["workspace_file"] = f"examples/{fname}"
            if dst.is_file() and dst.read_text(encoding="utf-8", errors="replace") != code:
                result["note"] = "Workspace copy differs (edited?) and was left unchanged."
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(code, encoding="utf-8")
            if not inline:
                result.setdefault("note", f"Source not inlined; read it with openscad_read(\"examples/{fname}\").")
        return result

    @tool(mcp, annotations=READ_ONLY)
    async def openscad_list_libraries(ctx: Context) -> dict[str, Any]:
        """List all installed OpenSCAD libraries with descriptions and usage examples.

        Libraries are auto-loaded via OPENSCADPATH. Use them with:
          use <LibraryName/module.scad>
          include <LibraryName/module.scad>
        """
        client = get_client(ctx)
        libs = []
        if client.libraries.is_dir():
            for lib_dir in sorted(client.libraries.iterdir()):
                if lib_dir.is_dir() and not lib_dir.name.startswith("."):
                    libs.append(_library_entry(lib_dir))
        bundled = client.bundled_library_dir()
        if bundled:
            for lib_dir in sorted(bundled.iterdir()):
                if lib_dir.is_dir() and not lib_dir.name.startswith(".") and all(lib["name"] != lib_dir.name for lib in libs):
                    entry = _library_entry(lib_dir)
                    entry["bundled"] = True
                    if lib_dir.name == "MCAD":
                        entry["use_example"] = "use <MCAD/gears.scad>"
                    libs.insert(0, entry)
        return {"libraries": libs, "count": len(libs), "library_path": str(client.libraries)}

    @tool(mcp, annotations=READ_ONLY)
    async def openscad_library_info(ctx: Context, library_name: str) -> dict[str, Any]:
        """Get detailed info about a specific library: files, README excerpt, usage.

        Args:
            library_name: Name of the library (e.g. "BOSL2", "NopSCADlib", "MCAD").
        """
        client = get_client(ctx)
        lib_dir = None
        # A library is a direct child of a libraries directory (it may itself be a symlink).
        if Path(library_name).name == library_name and library_name not in ("", ".", ".."):
            for base in (client.libraries, client.bundled_library_dir()):
                if base and (base / library_name).is_dir():
                    lib_dir = base / library_name
                    break
        if lib_dir is None:
            fail(f"Library not found: {library_name}")
        scad_files = sorted(lib_dir.rglob("*.scad"))
        file_tree: dict[str, list[str]] = {}
        for f in scad_files:
            rel = f.relative_to(lib_dir)
            parent = str(rel.parent) if str(rel.parent) != "." else "/"
            file_tree.setdefault(parent, []).append(rel.name)
        readme = None
        for readme_name in ("README.md", "readme.md", "README.txt", "README"):
            readme_path = lib_dir / readme_name
            if readme_path.exists():
                content = readme_path.read_text(encoding="utf-8", errors="replace")
                readme = content[:2000] + ("..." if len(content) > 2000 else "")
                break
        return {
            "name": library_name,
            "description": _LIBRARY_INFO.get(library_name, "Community library"),
            "path": str(lib_dir),
            "total_scad_files": len(scad_files),
            "file_tree": file_tree,
            "readme_excerpt": readme,
            "usage": f"use <{library_name}/filename.scad>",
        }

    @tool(mcp, annotations=OVERWRITES)
    async def openscad_clear_cache(ctx: Context) -> dict[str, Any]:
        """Delete cached meshes and generated scratch files; reports space freed."""
        client = get_client(ctx)
        return client.clear_cache()
