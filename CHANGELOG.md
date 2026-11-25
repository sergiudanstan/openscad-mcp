# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
