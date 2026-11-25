"""Parse OpenSCAD console output, customizer parameters and literal values."""

from __future__ import annotations

import json
import math
import re
from typing import Any

# Lines that carry no diagnostic value for a model author.
_NOISE = (
    "CGAL Cache",
    "Geometries in cache:",
    "Geometry cache size in bytes:",
    "CGAL Polyhedrons in cache:",
    "CGAL cache size in bytes:",
    "Compiling design",
    "Normalized CSG tree has",
    "Rendering Polygon Mesh using CGAL",
    "Rendering cache",
    "Loaded design",
    "Parsing design",
    "Rendering design",
)

_LOC = re.compile(r'in file "?(?P<file>[^,"]+?)"?, line (?P<line>\d+)')
_STATS = re.compile(r"^\s*(Simple|Vertices|Halfedges|Edges|Halffacets|Facets|Volumes|Contours):\s*(\S+)")

MAX_LINES = 200
MAX_CHARS = 20_000


def strip_noise(text: str) -> str:
    return "\n".join(ln for ln in text.splitlines() if not ln.strip().startswith(_NOISE))


def truncate(text: str, max_lines: int = MAX_LINES, max_chars: int = MAX_CHARS) -> str:
    """Cap console output so a chatty model cannot flood the client's context."""
    lines = text.splitlines()
    out = "\n".join(lines[:max_lines])
    if len(out) > max_chars:
        out = out[:max_chars]
    dropped = len(lines) - len(out.splitlines())
    if dropped > 0:
        out += f"\n... [{dropped} more lines truncated]"
    return out


def parse_output(text: str) -> dict[str, Any]:
    """Split OpenSCAD output into errors, warnings, echo lines and render stats.

    OpenSCAD exits 0 on failed asserts and unknown modules, so callers must
    judge success from `errors`, not only the exit code.
    """
    errors: list[dict] = []
    warnings: list[dict] = []
    echo: list[str] = []
    stats: dict[str, Any] = {}
    notes: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(_NOISE):
            continue
        if line.startswith("ECHO:"):
            echo.append(line[5:].strip())
            continue
        m = _STATS.match(raw)
        if m:
            v = m.group(2)
            stats[m.group(1).lower()] = int(v) if v.isdigit() else v
            continue
        if line.startswith("Total rendering time:"):
            stats["render_time"] = line.split(":", 1)[1].strip()
            continue
        if line.startswith("Top level object is a"):
            stats["dimension"] = 3 if "3D" in line else 2
            continue
        severity = None
        if line.startswith("ERROR:"):
            severity, body = "error", line[6:].strip()
        elif line.startswith("WARNING:"):
            severity, body = "warning", line[8:].strip()
        elif line.startswith("Can't parse file") or line.startswith("Current top level object is"):
            severity, body = ("warning" if "empty" in line or "not a 3D" in line else "error"), line
        elif line.startswith("TRACE:"):
            if errors or warnings:
                (errors or warnings)[-1].setdefault("trace", []).append(line[6:].strip())
            continue
        if severity is None:
            notes.append(line)
            continue
        item: dict[str, Any] = {"message": body}
        loc = _LOC.search(body)
        if loc:
            item["file"] = loc.group("file")
            item["line"] = int(loc.group("line"))
        (errors if severity == "error" else warnings).append(item)
    return {"errors": errors, "warnings": warnings, "echo": echo, "stats": stats, "other": notes}


# ----------------------------------------------------------------------
# Values -> OpenSCAD literals
# ----------------------------------------------------------------------

_RAW_LITERAL = re.compile(r"^\s*(-?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?|true|false|undef)\s*$")


def to_literal(value: Any) -> str:
    """Serialise a Python/JSON value as an OpenSCAD literal for -D.

    Strings that already are numbers, booleans, undef, vectors ("[...]") or
    quoted strings pass through unchanged (keeps {"size": "10"} working);
    any other string becomes an OpenSCAD string literal.
    """
    if value is None:
        return "undef"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"Non-finite number not allowed: {value}")
        return repr(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(to_literal(v) for v in value) + "]"
    if isinstance(value, str):
        s = value.strip()
        if _RAW_LITERAL.match(s) or (s.startswith("[") and s.endswith("]")) or (
            len(s) >= 2 and s.startswith('"') and s.endswith('"')
        ):
            return s
        return json.dumps(value)  # JSON string escaping matches OpenSCAD's
    raise ValueError(f"Unsupported parameter type: {type(value).__name__}")


def define_args(parameters: dict[str, Any] | None) -> list[str]:
    args: list[str] = []
    for k, v in (parameters or {}).items():
        if not re.fullmatch(r"\$?[A-Za-z_][A-Za-z0-9_]*", k):
            raise ValueError(f"Invalid parameter name: {k!r}")
        args += ["-D", f"{k}={to_literal(v)}"]
    return args


# ----------------------------------------------------------------------
# Customizer parameters
# ----------------------------------------------------------------------

def _strip_strings_and_comments(src: str) -> str:
    """Blank out comments and string contents, keeping offsets and newlines."""
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if src.startswith("//", i):
            j = src.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        elif src.startswith("/*", i):
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append("".join(ch if ch == "\n" else " " for ch in src[i:j]))
            i = j
        elif c == '"':
            j = i + 1
            while j < n and src[j] != '"':
                j += 2 if src[j] == "\\" else 1
            j = min(j + 1, n)
            out.append('"' + " " * max(0, j - i - 2) + ('"' if j - i >= 2 else ""))
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


_ASSIGN = re.compile(r"(?m)^[ \t]*(\$?[A-Za-z_]\w*)[ \t]*=[ \t]*([^;]*);")
_GROUP = re.compile(r"/\*\s*\[([^\]]+)\]\s*\*/")
_DEF = re.compile(r"(?m)^[ \t]*(module|function)\b")


def _parse_value(text: str) -> tuple[bool, Any]:
    t = text.strip()
    if t in ("true", "false"):
        return True, t == "true"
    try:
        return True, json.loads(t)  # numbers, strings, flat/nested vectors
    except (json.JSONDecodeError, ValueError):
        return False, t


def extract_parameters(src: str) -> list[dict[str, Any]]:
    """Customizer-style parameters: top-level literal assignments before the
    first module/function definition, with `// [range]` hints, trailing
    descriptions and `/* [Group] */` headings. `/* [Hidden] */` is skipped."""
    clean = _strip_strings_and_comments(src)
    stop = _DEF.search(clean)
    limit = stop.start() if stop else len(src)
    groups = [(m.start(), m.group(1).strip()) for m in _GROUP.finditer(src[:limit])]
    lines = src.splitlines()
    params: list[dict[str, Any]] = []
    depth = 0
    pos = 0
    for m in _ASSIGN.finditer(clean[:limit]):
        depth += clean[pos:m.start()].count("{") - clean[pos:m.start()].count("}")
        pos = m.start()
        if depth != 0:
            continue
        name = m.group(1)
        literal, value = _parse_value(src[m.start(2):m.end(2)])
        if not literal:
            continue
        group = None
        for gpos, gname in groups:
            if gpos < m.start():
                group = gname
        if group and group.lower() == "hidden":
            continue
        line_end = src.find("\n", m.end())
        tail = src[m.end(): len(src) if line_end < 0 else line_end].strip()
        item: dict[str, Any] = {
            "name": name,
            "value": value,
            "type": type(value).__name__ if not isinstance(value, list) else "vector",
            "line": src.count("\n", 0, m.start()) + 1,
        }
        if group:
            item["group"] = group
        if tail.startswith("//"):
            hint = tail[2:].strip()
            r = re.match(r"\[([^\]]*)\]", hint)
            if r:
                item["constraint"] = r.group(1).strip()
                hint = hint[r.end():].strip()
            if hint:
                item["description"] = hint
        # Description comment on the line directly above
        lineno = item["line"]
        prev = lines[lineno - 2].strip() if lineno >= 2 else ""
        if "description" not in item and prev.startswith("//") and not prev.startswith("// ["):
            item["description"] = prev[2:].strip()
        params.append(item)
    return params
