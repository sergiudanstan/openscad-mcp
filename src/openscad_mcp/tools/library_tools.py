"""Library tools: listing files, cheatsheet, version, syntax check, examples, library management."""

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP, Context

# Examples directory: openscad-mcp/examples/ (two package levels + src + project root)
_EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "examples"

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


def register_library_tools(mcp: FastMCP) -> None:
    """Register library / utility tools with the MCP server."""

    @mcp.tool()
    async def openscad_list_files(ctx: Context) -> str:
        """List all .scad files currently in the workspace."""
        try:
            client = ctx.request_context.lifespan_context["client"]
            files = sorted(p.name for p in client.workspace.glob("**/*.scad"))
            return json.dumps({"files": files, "count": len(files)})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def openscad_cheatsheet(ctx: Context) -> str:
        """Return an OpenSCAD language quick reference / cheatsheet."""
        return _CHEATSHEET

    @mcp.tool()
    async def openscad_version(ctx: Context) -> str:
        """Get the installed OpenSCAD version."""
        try:
            client = ctx.request_context.lifespan_context["client"]
            version_text = await client.version()
            return json.dumps({"version": version_text})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def openscad_check_syntax(ctx: Context, filename: str) -> str:
        """Dry-run a .scad file to check for syntax errors without rendering.

        Args:
            filename: Name of the .scad file (relative to workspace).
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            rc, stdout, stderr = await client.check_syntax(filename)
            passed = rc == 0
            return json.dumps({
                "filename": filename,
                "passed": passed,
                "returncode": rc,
                "stdout": stdout,
                "stderr": stderr,
                "errors": [line for line in stderr.splitlines() if "ERROR" in line.upper()],
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def openscad_list_examples(ctx: Context) -> str:
        """List built-in example .scad files shipped with the server."""
        try:
            if not _EXAMPLES_DIR.exists():
                return json.dumps({"examples": [], "note": "examples/ directory not found"})
            examples = sorted(p.name for p in _EXAMPLES_DIR.glob("*.scad"))
            return json.dumps({
                "examples": examples,
                "count": len(examples),
                "directory": str(_EXAMPLES_DIR),
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def openscad_list_libraries(ctx: Context) -> str:
        """List all installed OpenSCAD libraries with descriptions and usage examples.

        Libraries are auto-loaded via OPENSCADPATH. Use them with:
          use <LibraryName/module.scad>
          include <LibraryName/module.scad>
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            libs = []
            for lib_dir in sorted(client.libraries.iterdir()):
                if lib_dir.is_dir() and not lib_dir.name.startswith("."):
                    name = lib_dir.name
                    # Count .scad files
                    scad_files = list(lib_dir.rglob("*.scad"))
                    # Find main entry point
                    main_files = [f for f in scad_files if f.stem.lower() in (
                        name.lower(), "main", "std", "core", "lib", "all"
                    )]
                    entry = main_files[0].relative_to(lib_dir) if main_files else None
                    libs.append({
                        "name": name,
                        "description": _LIBRARY_INFO.get(name, "Community library"),
                        "scad_files": len(scad_files),
                        "entry_point": str(entry) if entry else None,
                        "use_example": f'use <{name}/{entry}>' if entry else f'use <{name}/...>',
                        "path": str(lib_dir),
                    })

            # Also check for MCAD in app bundle
            mcad_path = Path("/Applications/OpenSCAD-2021.01.app/Contents/Resources/libraries/MCAD")
            if mcad_path.is_dir():
                scad_files = list(mcad_path.rglob("*.scad"))
                libs.insert(0, {
                    "name": "MCAD",
                    "description": _LIBRARY_INFO.get("MCAD", "Built-in library"),
                    "scad_files": len(scad_files),
                    "entry_point": None,
                    "use_example": 'use <MCAD/gears.scad>',
                    "path": str(mcad_path),
                })

            return json.dumps({
                "libraries": libs,
                "count": len(libs),
                "library_path": str(client.libraries),
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def openscad_library_info(ctx: Context, library_name: str) -> str:
        """Get detailed info about a specific library: files, modules, usage.

        Args:
            library_name: Name of the library (e.g. "BOSL2", "NopSCADlib", "SCON").
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            lib_dir = client.libraries / library_name
            if not lib_dir.is_dir():
                return json.dumps({"error": f"Library not found: {library_name}"})

            # Collect all .scad files organized by subdirectory
            scad_files = sorted(lib_dir.rglob("*.scad"))
            file_tree = {}
            for f in scad_files:
                rel = f.relative_to(lib_dir)
                parent = str(rel.parent) if str(rel.parent) != "." else "/"
                if parent not in file_tree:
                    file_tree[parent] = []
                file_tree[parent].append(rel.name)

            # Read README if available
            readme = None
            for readme_name in ("README.md", "readme.md", "README.txt", "README"):
                readme_path = lib_dir / readme_name
                if readme_path.exists():
                    content = readme_path.read_text(encoding="utf-8", errors="replace")
                    # Truncate to first 2000 chars
                    readme = content[:2000] + ("..." if len(content) > 2000 else "")
                    break

            return json.dumps({
                "name": library_name,
                "description": _LIBRARY_INFO.get(library_name, "Community library"),
                "path": str(lib_dir),
                "total_scad_files": len(scad_files),
                "file_tree": file_tree,
                "readme_excerpt": readme,
                "usage": f'use <{library_name}/filename.scad>',
            })
        except Exception as e:
            return json.dumps({"error": str(e)})
