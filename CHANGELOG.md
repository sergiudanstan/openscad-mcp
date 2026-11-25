# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-11-25

### Added
- Previews come back as MCP images (several standard views per call, rendered in parallel),
  with `--render`, edges and axes options.
- `openscad_measure`: exact bbox, volume, surface area, centroid, watertightness, body count and
  mesh-health edge counts; area, perimeter and bbox for 2D models.
- Engineering tools: `openscad_mass_properties` (mass, COM, inertia tensor, principal moments),
  `openscad_interference` (overlap volume between two parts), `openscad_section` (cut area, 2D
  bbox, image), `openscad_print_report` (overhangs, bed contact, build volume).
- `openscad_eval` (expressions in a model's scope), `openscad_get_parameters` (customizer
  parameters), `openscad_get_example`, `openscad_clear_cache`.
- `openscad_edit` accepts an exact `old_string` → `new_string` replacement and an etag guard.
- Mesh cache keyed by the file and every file it includes or imports (`-d` dependency output).
- Automatic Manifold backend on OpenSCAD builds that have it; newest installed OpenSCAD is
  preferred; `OPENSCAD_BINARY`, `OPENSCAD_MCP_*` environment configuration.
- Animations are joined into an MP4 when ffmpeg is available; frame list in the result.
- Server instructions for clients, tool annotations, structured tool results; `openscad-mcp`
  console script (`uvx --from git+…`).
- Tests: geometry and parser unit tests, real-OpenSCAD tests for every tool with perturbation
  checks, MCP-protocol tests; CI runs them under xvfb so previews are exercised.

### Changed
- Migrated to the MCP Python SDK 2.x: `FastMCP` is now `MCPServer` (`mcp.server.mcpserver`), and the
  HTTP/SSE bind address and host validation are passed to `run()` instead of `mcp.settings`.
  The dependency is `mcp>=2.3.0,<3`; SDK 1.x is no longer supported.
- Tool errors are reported with `isError: true` (JSON payload) instead of a normal result.
- Parameters are typed: non-numeric strings become OpenSCAD strings; numeric strings and
  vectors still pass through as before.
- `openscad_check_syntax` fails on any `ERROR` (OpenSCAD exits 0 on failed asserts) and reports
  errors/warnings with file and line; `strict_passed` also requires no warnings.
- STL exports are binary. Console output is trimmed of cache chatter and capped in size.
- Examples moved into the package (`src/openscad_mcp/examples/`) so wheel installs include them.
- Default render timeout 300 s (was 60 s), configurable per call.

### Fixed
- `openscad_list_files` walked into every symlinked library and returned bare names; it now
  lists workspace files only, with relative paths.
- The server no longer fails to start when OpenSCAD is missing; tools explain the problem.
- MCAD is found next to whichever OpenSCAD binary is used, not one hard-coded app path.
- Importing `openscad_mcp.__main__` no longer starts the server, so the console script runs it once.

## [0.2.0] - 2026-11-25

`openscad-mcp` is an MCP server that lets an AI assistant write, check, render and export
OpenSCAD models through the local `openscad` CLI: 14 tools (create/read/edit files, export to
STL/3MF/OFF/AMF/DXF/SVG/PDF, PNG previews, animation frames, render statistics, syntax check,
cheatsheet, examples, installed libraries). It runs over stdio, or over HTTP (Dockerfile and
Render blueprint included).

### Added
- Tests that run the real OpenSCAD CLI and the registered tools end to end (create/read, syntax
  check, STL export and parameter override, render info, path confinement).
- CI (tests on Python 3.10 and 3.13 from `uv.lock` with OpenSCAD installed, ruff, `pip-audit`,
  `zizmor`), CodeQL, OpenSSF Scorecard and a tag-triggered release workflow with CycloneDX SBOM
  and build provenance; Dependabot for actions, uv and Docker.
- `SECURITY.md` (threat model for a server that evaluates model-written OpenSCAD and has an
  unauthenticated HTTP mode), `CONTRIBUTING.md` and this changelog.
- README lists `openscad_list_libraries` and `openscad_library_info`, and its security notes
  now state the HTTP-mode caveat.

### Fixed
- `OpenSCADClient.resolve_path` accepted a sibling directory sharing the workspace's name prefix
  (`~/openscad-mcp-workspace-evil`); it now uses a real path-containment check.
- `openscad_library_info` joined the caller's `library_name` onto the libraries directory
  unchecked, so `../something` listed `.scad` files and returned a README excerpt from outside it;
  names that are not a direct child are now refused.

### Changed
- `uv.lock` refreshed: the previous lock pinned versions with known vulnerabilities
  (`pip-audit` reported 60 findings across 8 packages, including `starlette`, `cryptography`,
  `anyio`, `certifi`); the `mcp` SDK stays on 1.x as declared.

[Unreleased]: https://github.com/sergiudanstan/openscad-mcp/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/sergiudanstan/openscad-mcp/releases/tag/v0.2.0
