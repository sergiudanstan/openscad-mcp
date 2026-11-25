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

Connect this server to Claude Desktop and you can ask Claude to:

- **Design** parametric 3D models in OpenSCAD
- **Preview** renders as PNG images
- **Export** to STL, 3MF, AMF, DXF, SVG, and more
- **Animate** models using OpenSCAD's `$t` variable
- **Check syntax** before rendering
- **Browse** an OpenSCAD language cheatsheet

## Available Tools

| Tool | Description |
|------|-------------|
| `openscad_create` | Create a new `.scad` file |
| `openscad_read` | Read an existing `.scad` file |
| `openscad_edit` | Update an existing `.scad` file |
| `openscad_export` | Export to STL, 3MF, OFF, AMF, DXF, SVG, PDF |
| `openscad_preview` | Render a PNG preview with camera/color options |
| `openscad_render_animated` | Render animation frames using `$t` |
| `openscad_get_info` | Get model render statistics |
| `openscad_list_files` | List `.scad` files in the workspace |
| `openscad_check_syntax` | Dry-run syntax validation |
| `openscad_cheatsheet` | OpenSCAD language quick reference |
| `openscad_version` | Get installed OpenSCAD version |
| `openscad_list_examples` | List built-in example files |
| `openscad_list_libraries` | List installed OpenSCAD libraries |
| `openscad_library_info` | Files and README excerpt of one installed library |

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
```

Start a new Claude Code session and the `openscad_*` tools will be available.

## Examples

The `examples/` directory includes sample `.scad` files:

- **box.scad** — Simple parametric box
- **gear.scad** — Involute spur gear
- **vase.scad** — Curved vase with twist

## Project Structure

```
openscad-mcp/
├── src/openscad_mcp/
│   ├── server.py           # FastMCP server setup
│   ├── client.py           # OpenSCAD CLI wrapper
│   └── tools/
│       ├── design_tools.py   # create / read / edit
│       ├── render_tools.py   # preview / export / animate
│       └── library_tools.py  # list files / cheatsheet / syntax check
├── examples/               # Sample .scad files
├── tests/                  # Test suite
└── pyproject.toml
```

## Security

- **No shell injection** — uses `subprocess_exec` (argument list, not shell string)
- **Path traversal protection** — file names passed to the tools are confined to the workspace directory
- **No credentials or API keys** — runs locally and makes no outgoing network calls
- **HTTP mode is unauthenticated** — with `MCP_TRANSPORT=streamable-http` or `sse` the server listens on `0.0.0.0` with host validation disabled; see [SECURITY.md](SECURITY.md) before exposing it

## Workspace

All files are created in `~/openscad-mcp-workspace/` by default.

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/   # tests that run the real CLI need `openscad` on PATH
```

## Full Installation Guide

See [openscad-mcp-install-guide.pdf](openscad-mcp-install-guide.pdf) for detailed step-by-step instructions for macOS and Windows.

## Development

```bash
uv sync --locked --extra dev      # or: pip install -e ".[dev]"
uv run pytest -q tests            # real-CLI tests need `openscad` on PATH
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) and [CHANGELOG.md](CHANGELOG.md).
