---
title: OpenSCAD MCP
emoji: "\U0001F4D0"
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# OpenSCAD MCP Server

[![CI](https://github.com/sergiudanstan/openscad-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/sergiudanstan/openscad-mcp/actions/workflows/ci.yml)
[![CodeQL](https://github.com/sergiudanstan/openscad-mcp/actions/workflows/codeql.yml/badge.svg)](https://github.com/sergiudanstan/openscad-mcp/actions/workflows/codeql.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/sergiudanstan/openscad-mcp/badge)](https://scorecard.dev/viewer/?uri=github.com/sergiudanstan/openscad-mcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An MCP (Model Context Protocol) server that lets AI assistants like Claude create, edit, render, and export 3D models using [OpenSCAD](https://openscad.org/).

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)

## What It Does

Connect this server to Claude Desktop or Claude Code and you can ask Claude to:

- **Design** parametric 3D models in OpenSCAD, editing them with small exact-snippet replacements
- **See** its work: previews come back as images, several standard views per call, rendered in parallel
- **Measure** exactly: bounding box, volume, surface area, centroid, watertightness, separate bodies (2D: area, perimeter)
- **Analyse** like an engineer: mass, centre of mass and inertia; interference between two parts;
  section cuts for wall thickness; an FDM print report (overhangs, bed contact, build volume)
- **Check** models with errors and warnings tied to file and line — including failed `assert()`s,
  which OpenSCAD itself exits 0 on
- **Export** to STL (binary), 3MF, OFF, AMF, DXF, SVG, PDF, CSG; **animate** `$t` to PNG frames + MP4

Each model is rendered once per parameter set: the mesh is cached by the content of the file **and
everything it includes or imports**, and measure, mass, print report, section, interference, STL export
and render statistics all reuse it. Parallel calls for the same model share one render. On the bundled
`gear_train.scad` with OpenSCAD 2021.01 (CGAL), measure → export STL → get_info → section took 145 s in
v0.3 (every step re-rendered) and takes 36 s now, all of it the first render. With an OpenSCAD build that
has the Manifold backend, the server uses it automatically.

Results are kept small for the model reading them: repeated warnings are merged into one entry with a
line list, echo output is capped (all of it in `openscad_check_syntax`), and multi-view previews use
512×384 tiles unless a size is given.

## Available Tools

| Tool | Description |
|------|-------------|
| `openscad_create` | Create a `.scad` file (returns an etag) |
| `openscad_read` | Read a `.scad` file, optionally with line numbers |
| `openscad_edit` | Replace the whole file, or an exact `old_string` → `new_string`; optional etag guard |
| `openscad_get_parameters` | Customizer parameters: values, `[min:step:max]` constraints, descriptions, groups |
| `openscad_check_syntax` | Parse + evaluate without geometry; structured errors/warnings/echo with lines |
| `openscad_eval` | Evaluate expressions in a model's scope (`"wall*2 + clearance"`) |
| `openscad_preview` | PNG preview(s) returned as images; `views=["isometric","front","top","right",…]` |
| `openscad_measure` | Exact bbox, volume, area, centroid, watertight, bodies (2D: area, perimeter) |
| `openscad_mass_properties` | Mass, centre of mass, inertia tensor and principal moments for a material/density |
| `openscad_interference` | Overlap volume/bbox between two parts, or clear / touching; ray-sampled estimate when CGAL cannot intersect them |
| `openscad_section` | Cut at `axis=offset`: section area, 2D bbox, regions and an image (sliced in Python, works on non-manifold meshes) |
| `openscad_print_report` | Overhang area, bed contact, build-volume fit, issues list |
| `openscad_export` | Export to STL, 3MF, OFF, AMF, DXF, SVG, PDF, CSG, ECHO, AST, PNG |
| `openscad_render_animated` | Frames from `$t`, joined into an MP4 when ffmpeg is available |
| `openscad_get_info` | Render statistics (from the cached render) |
| `openscad_list_files` | `.scad` files in the workspace (relative paths, libraries skipped) |
| `openscad_list_examples` / `openscad_get_example` | Bundled examples; copy one into the workspace |
| `openscad_list_libraries` / `openscad_library_info` | Installed libraries (incl. bundled MCAD) |
| `openscad_cheatsheet` | OpenSCAD language quick reference |
| `openscad_version` | Version, binary, backend (cgal/manifold), paths |
| `openscad_clear_cache` | Drop cached meshes |

Parameters are typed JSON — `{"width": 40, "label": "A", "holes": [3, 5], "solid": true}`; strings that
already are numbers or vectors (`"10"`, `"[1,2]"`) pass through unchanged. Errors come back with
`isError: true`. Tools carry MCP annotations (read-only vs. writing), and the server sends usage
instructions to the client.

## Quick Start

### Prerequisites

- **Python 3.10+**
- **OpenSCAD** installed ([download](https://openscad.org/downloads.html))
- **Claude Desktop** ([download](https://claude.ai/download))

### Install

```bash
git clone https://github.com/sergiudanstan/openscad-mcp.git
cd openscad-mcp
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e .
```

### Configure Claude Desktop

Add to your Claude Desktop config:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "openscad": {
      "command": "/full/path/to/openscad-mcp/.venv/bin/python",
      "args": ["-m", "openscad_mcp"]
    }
  }
}
```

> On Windows, use `".venv\\Scripts\\python.exe"` instead.

Restart Claude Desktop — the OpenSCAD tools will appear in the hammer icon.

### Configure Claude Code

```bash
claude mcp add openscad -s user -- /full/path/to/openscad-mcp/.venv/bin/python -m openscad_mcp
# or, without a clone (the PyPI name `openscad-mcp` belongs to a different project):
uv tool install git+https://github.com/sergiudanstan/openscad-mcp
claude mcp add openscad -s user -- ~/.local/bin/openscad-mcp     # update later: uv tool upgrade openscad-mcp
```

`uvx --from git+https://github.com/sergiudanstan/openscad-mcp openscad-mcp` also works, but it asks
GitHub for the latest commit on every start (about 0.5 s slower) and the server does not start offline.

Start a new Claude Code session and the `openscad_*` tools will be available.

## Examples

`src/openscad_mcp/examples/` ships 14 sample models (box, gear, vase, linkages, gear train, mobile
robot, pick-and-place arm, factory assembly, …); they are packaged, so `openscad_get_example` works
in a wheel install too. Every one is parsed in the test suite.

## Project Structure

```
openscad-mcp/
├── src/openscad_mcp/
│   ├── server.py           # MCPServer setup and instructions
│   ├── client.py           # OpenSCAD CLI wrapper, discovery, mesh cache
│   ├── geometry.py         # pure-Python mesh/2D analysis (no extra dependencies)
│   ├── diagnostics.py      # console parsing, typed parameters, customizer extraction
│   ├── examples/           # sample .scad files (packaged)
│   └── tools/
│       ├── design_tools.py   # create / read / edit / parameters
│       ├── render_tools.py   # preview / export / animate / info
│       ├── analysis_tools.py # measure / mass / interference / section / print report / eval
│       └── library_tools.py  # files / syntax check / examples / libraries / cache
├── tests/                  # Test suite
└── pyproject.toml
```

## Security

- **No shell injection** — uses `subprocess_exec` (argument list, not shell string)
- **Path traversal protection** — file names passed to the tools are confined to the workspace directory
- **No credentials or API keys** — runs locally and makes no outgoing network calls
- **HTTP mode is unauthenticated** — with `MCP_TRANSPORT=streamable-http` or `sse` the server listens on `0.0.0.0` with host validation disabled; see [SECURITY.md](SECURITY.md) before exposing it

## Configuration

| Variable | Default | Meaning |
|----------|---------|---------|
| `OPENSCAD_BINARY` | newest OpenSCAD found | Binary to use (PATH, `/Applications/OpenSCAD*.app`, `~/Applications`, Linux/Windows paths are searched) |
| `OPENSCAD_MCP_WORKSPACE` | `~/openscad-mcp-workspace` | Where files are created; all paths are confined to it |
| `OPENSCAD_MCP_LIBRARIES` | `~/Documents/OpenSCAD/libraries` | Extra libraries, put on `OPENSCADPATH` |
| `OPENSCAD_MCP_CACHE` | `~/.cache/openscad_mcp_render` | Mesh cache |
| `OPENSCAD_MCP_CACHE_MAX_MB` | `512` | Cache size cap; least recently used meshes go first |
| `OPENSCAD_MCP_TIMEOUT` | `300` | Default render timeout in seconds (tools also take `timeout`) |
| `OPENSCAD_MCP_JOBS` | CPUs − 1 | Maximum concurrent OpenSCAD processes |
| `OPENSCAD_MCP_BACKEND` | auto | Set `cgal` to disable Manifold on builds that have it |

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/   # tests that run the real CLI need `openscad` on PATH (Linux: run under xvfb-run for PNGs)
```

## Full Installation Guide

See [openscad-mcp-install-guide.pdf](openscad-mcp-install-guide.pdf) for detailed step-by-step instructions for macOS and Windows.

## Development

```bash
uv sync --locked --extra dev      # or: pip install -e ".[dev]"
uv run pytest -q tests            # real-CLI tests need `openscad` on PATH
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) and [CHANGELOG.md](CHANGELOG.md).
