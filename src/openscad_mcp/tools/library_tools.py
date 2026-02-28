"""Library tools: listing files, cheatsheet, version, syntax check, examples."""

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP, Context

# Examples directory: openscad-mcp/examples/ (two package levels + src + project root)
_EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "examples"

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
