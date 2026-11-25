# Security Policy

`openscad-mcp` is an MCP server that lets an AI assistant write, check, render and export
OpenSCAD models by driving the local `openscad` CLI. By default it talks MCP over stdio to the
client that launched it. It can also be started as an HTTP server (`MCP_TRANSPORT=streamable-http`
or `sse`), which is how the included `Dockerfile` and `render.yaml` deploy it.

## Supported versions

| Version | Supported |
|---|---|
| 0.2.x | Current |

Single maintainer; only the latest release receives fixes.

## Reporting a vulnerability

**Please do not open a public issue for a security problem.** Report it privately:
**[Report a vulnerability](https://github.com/sergiudanstan/openscad-mcp/security/advisories/new)**
(Security -> Advisories -> Report a vulnerability).

| Stage | Target |
|---|---|
| Acknowledgement | within 3 business days |
| Triage | within 10 business days |
| Fix, or a documented decision not to fix | within 90 days |

These are best-effort targets from a single unpaid maintainer, not a contractual SLA.
There is no bug bounty; credit is offered in the advisory and changelog.

## Threat model

Tool arguments are untrusted: they are chosen by an LLM that may itself be steered by
prompt injection in content it reads. What the tools can do with them:

- **File-system reach.** Every tool that takes a file name goes through
  `OpenSCADClient.resolve_path`, which confines it to the workspace
  (`~/openscad-mcp-workspace/`) and rejects `..` and absolute paths outside it; the tests
  cover traversal, absolute paths and a sibling directory sharing the workspace's name
  prefix. `openscad_library_info` accepts only a direct child name of the libraries
  directory. Files the server writes there (`.scad`, exports, previews, summaries) are
  created with the caller's content.
- **Code execution.** No shell is involved: OpenSCAD is started with an argument list
  (`asyncio.create_subprocess_exec`), and `parameters` are passed as separate `-D name=value`
  arguments. The caller does, however, control the **content of the `.scad` file that
  OpenSCAD then evaluates**. OpenSCAD has no command-execution feature, but a model can read
  other files on the machine (`import()`, `surface()`, `include`/`use` of paths outside the
  workspace) and consume CPU and memory. Renders are killed after 60 s (animations after
  5 s per frame; the frame count is caller-chosen). There is no memory limit.
- **Network.** The server makes no outgoing network calls.
- **HTTP mode has no authentication.** With `streamable-http` or `sse` the server listens on
  `0.0.0.0` (override with `MCP_HOST`) and `__main__.py` switches off the MCP SDK's
  DNS-rebinding protection and accepts any `Host`/`Origin` so it works behind a hosting
  proxy. Anyone who can reach that port can create files in the workspace and run OpenSCAD
  on them. Do not expose it on a network you do not control without putting your own
  authentication in front of it, and treat any deployment made from `render.yaml` as an open
  service.

## Scope

In scope:

- A way to read or write outside the workspace (or outside the libraries directory for
  `openscad_library_info`) through any tool.
- Command or argument injection into the `openscad` process.
- Anything in this repository's workflows that could publish a release not built from `main`.

Out of scope:

- The lack of authentication in HTTP mode, and the disabled host validation: both are
  documented above. Reports of "an unauthenticated client can use the server" are not
  vulnerabilities; reports of a bypass of the path confinement from such a client are.
- A `.scad` model reading files it is pointed at, or using a lot of CPU: that is OpenSCAD's
  behaviour; see the threat model.
- Vulnerabilities in OpenSCAD itself, the MCP SDK or the client (report upstream).

## Supply chain

CI runs the test suite on Python 3.10 and 3.13 against a real OpenSCAD CLI with
dependencies installed from `uv.lock`, `ruff` (syntax and undefined-name checks only),
`pip-audit` on the locked dependencies and on the hash-pinned CI toolchain, CodeQL, and
`zizmor` on the workflows. Actions are pinned to full commit SHAs and kept current by
Dependabot. Releases attach a source archive and a CycloneDX SBOM of the locked runtime
dependencies, both with Sigstore build provenance:

```
gh attestation verify openscad-mcp-v0.2.0.tar.gz --repo sergiudanstan/openscad-mcp
```

The `Dockerfile` installs OpenSCAD and Xvfb from the Debian package repository and runs the
server as a non-root user; its base image tag is not digest-pinned.
