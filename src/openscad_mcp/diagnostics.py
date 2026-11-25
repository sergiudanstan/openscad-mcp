"""Parse OpenSCAD console output, customizer parameters and literal values."""

from __future__ import annotations

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
    "Fontconfig warning:",
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

_NUM = re.compile(r"[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?")
_UNESCAPE = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}


class _LiteralParser:
    """Parser for OpenSCAD literal values: numbers, true/false/undef, strings,
    vectors (trailing comma allowed) and ranges [a:b] / [a:s:b]. Comments
    between tokens are allowed. Anything else (expressions) is rejected."""

    def __init__(self, text: str) -> None:
        self.t = text
        self.i = 0

    def ws(self) -> None:
        while True:
            m = re.compile(r"\s+|//[^\n]*|/\*.*?\*/", re.S).match(self.t, self.i)
            if not m or m.end() == self.i:
                return
            self.i = m.end()

    def value(self) -> Any:
        self.ws()
        t, i = self.t, self.i
        if t.startswith("[", i):
            self.i += 1
            items: list[Any] = []
            self.ws()
            if t.startswith("]", self.i):
                self.i += 1
                return items
            first = self.value()
            self.ws()
            if t.startswith(":", self.i) and isinstance(first, (int, float)):
                parts = [first]
                while t.startswith(":", self.i):
                    self.i += 1
                    v = self.value()
                    if not isinstance(v, (int, float)) or isinstance(v, bool):
                        raise ValueError("range bounds must be numbers")
                    parts.append(v)
                    self.ws()
                if len(parts) > 3 or not t.startswith("]", self.i):
                    raise ValueError("bad range")
                self.i += 1
                return {"range": parts}
            items.append(first)
            while True:
                self.ws()
                if t.startswith("]", self.i):
                    self.i += 1
                    return items
                if not t.startswith(",", self.i):
                    raise ValueError("expected , or ]")
                self.i += 1
                self.ws()
                if t.startswith("]", self.i):  # trailing comma
                    self.i += 1
                    return items
                items.append(self.value())
        if t.startswith('"', i):
            out, j = [], i + 1
            while j < len(t) and t[j] != '"':
                if t[j] == "\\" and j + 1 < len(t):
                    nxt = t[j + 1]
                    if nxt in _UNESCAPE:
                        out.append(_UNESCAPE[nxt])
                        j += 2
                        continue
                    m = re.compile(r"x([0-7][0-9a-fA-F])|u([0-9a-fA-F]{4})|U([0-9a-fA-F]{6})").match(t, j + 1)
                    if m:
                        out.append(chr(int(next(g for g in m.groups() if g), 16)))
                        j = m.end()
                        continue
                out.append(t[j])
                j += 1
            if j >= len(t):
                raise ValueError("unterminated string")
            self.i = j + 1
            return "".join(out)
        for word, val in (("true", True), ("false", False), ("undef", None)):
            if t.startswith(word, i) and not re.match(r"\w", t[i + len(word): i + len(word) + 1]):
                self.i = i + len(word)
                return val
        m = _NUM.match(t, i)
        if m and not re.match(r"[\w.]", t[m.end(): m.end() + 1]):
            self.i = m.end()
            num = float(m.group(0))
            return int(num) if re.fullmatch(r"[-+]?\d+", m.group(0)) else num
        raise ValueError("not a literal")


def parse_literal(text: str) -> Any:
    """Parse an OpenSCAD literal; raises ValueError for anything else."""
    p = _LiteralParser(text)
    v = p.value()
    p.ws()
    if p.i != len(text):
        raise ValueError("trailing text after literal")
    return v


def _scad_string(value: str) -> str:
    out = []
    for ch in value:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\r":
            out.append("\\r")
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append(f"\\x{ord(ch):02x}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def to_literal(value: Any) -> str:
    """Serialise a Python/JSON value as an OpenSCAD literal for -D.

    Strings that already are a complete OpenSCAD literal (number, boolean,
    undef, vector, range or quoted string) pass through unchanged, which keeps
    {"size": "10"} working; any other string becomes an OpenSCAD string, so a
    value can never smuggle in statements.
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
        if s and ("//" not in s and "/*" not in s):
            try:
                parse_literal(s)
                return s
            except ValueError:
                pass
        return _scad_string(value)
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
    try:
        return True, parse_literal(text.strip())
    except ValueError:
        return False, text.strip()


def _type_name(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "vector"
    if isinstance(value, dict):
        return "range"
    return "undef"


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
            "type": _type_name(value),
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
