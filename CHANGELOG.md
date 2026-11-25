# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-11-26

### Changed
- One render per model and parameter set: `openscad_export` (STL) and `openscad_get_info` reuse the
  mesh cache instead of rendering again, and parallel calls for the same model share one render
  (cancelling every caller stops it). On `gear_train.scad` (OpenSCAD 2021.01, CGAL) measure → export →
  get_info → section went from 145 s to 36 s; export and get_info after a measure take milliseconds.
- `openscad_section` slices the cached mesh in Python instead of rendering `projection(cut=true)` of
  it with CGAL: 5.2 s → 0.02 s on `gear_train.scad` (0.2 s with the image). It agrees with the CGAL
  result on manifold models (area within 1e-6, same regions) and adds a note when the plane lies on a face.
- Results are smaller: warnings repeated on many lines are merged (`lines: [...]`), the message text
  no longer repeats file and line, echo is capped at 10 lines outside `openscad_check_syntax`
  (`echo_omitted` gives the rest), console lines that are not errors, warnings or echo (DEPRECATED,
  EXPORT-WARNING) come once each as `notes`, and the raw console dump (`stderr`/`console`) is only
  returned when nothing in it could be parsed. On `gear_train.scad` a measure result went from
  4.7k to 0.8k characters, get_info from 7.7k to 0.75k.
- `openscad_preview`: views of a multi-view call default to 512×384 (four cost what one 1024×768
  did); a single view stays 1024×768. When OpenSCAD reports errors the images are written but not
  returned (the scene is empty), and messages are reported once instead of once per view.
- `openscad_get_example` copies large examples into the workspace without inlining their source
  (the biggest was about 28k tokens); `include_content` forces either way. Results give `bytes` and `lines`.
- The server answers `initialize` without waiting for the OpenSCAD probe, which now runs `--version`
  and `--help` at once; a binary that does not answer is probed again later instead of being treated
  as featureless for the whole session.
- Mesh cache entries name their own immutable STL (`mesh.<tag>.stl`), and the cache is capped
  (`OPENSCAD_MCP_CACHE_MAX_MB`, default 512) with least-recently-used eviction; meshes no entry uses,
  leftovers of interrupted renders and scratch files unused for a day are swept.

### Fixed
- `openscad_section` and `openscad_interference` reported "the plane does not cut the model" and
  "touching_or_near" when CGAL refused to re-import a non-manifold mesh (for example gear teeth
  tangent to the body, three of the bundled examples). Sections now work on such meshes, and
  interference falls back to a ray-sampled estimate (`method: "ray_sampled"`, `resolution_mm`,
  `volume_error_bound`; `indeterminate` when an open mesh leaves the answer unknown), also when CGAL
  times out.
- A file saved just as a render finished could be cached with the new file's digest next to the
  old mesh, so the stale mesh was served until the next edit; the digest is now taken before the
  check for edits. A render that cannot be cached no longer replaces another process's entry.
- The cache key now includes the library search path and ignores the order of parameters.
- `openscad_preview(render=true)` always failed on OpenSCAD 2021.01: `--render` took the input file
  as its value.
- Stopping the server with SIGTERM/SIGHUP left running OpenSCAD renders behind for minutes; they are
  killed first. A workspace that cannot be created is reported by the tools instead of stopping the
  server. `openscad_eval` and 2D measurement no longer leak (or share) temporary files.

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
- Animations render each frame as its own run in parallel (OpenSCAD 2021 `--animate` crashes
  under Xvfb) and are joined into an MP4 when ffmpeg is available; frame list in the result.
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
