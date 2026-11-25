"""Subprocess wrapper for the OpenSCAD CLI: discovery, runner, mesh cache."""

from __future__ import annotations

import asyncio
import glob
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openscad_mcp import diagnostics

logger = logging.getLogger(__name__)


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser() if raw else default


DEFAULT_WORKSPACE = _env_path("OPENSCAD_MCP_WORKSPACE", Path.home() / "openscad-mcp-workspace")
DEFAULT_LIBRARIES = _env_path("OPENSCAD_MCP_LIBRARIES", Path.home() / "Documents" / "OpenSCAD" / "libraries")
DEFAULT_CACHE = _env_path("OPENSCAD_MCP_CACHE", Path.home() / ".cache" / "openscad_mcp_render")
RENDER_TIMEOUT = float(os.environ.get("OPENSCAD_MCP_TIMEOUT", "300"))  # seconds
CACHE_MAX_MB = float(os.environ.get("OPENSCAD_MCP_CACHE_MAX_MB", "512"))
PROBE_RETRY_S = 30.0
SWEEP_EVERY_S = 60.0

_VERSION_RE = re.compile(r"(\d{4})\.(\d{1,2})(?:\.(\d{1,2}))?")


def parse_version(text: str) -> tuple[int, ...]:
    m = _VERSION_RE.search(text or "")
    return tuple(int(g) for g in m.groups() if g is not None) if m else ()


@dataclass
class Features:
    """What the installed OpenSCAD supports (probed from --help)."""

    version: tuple[int, ...] = ()
    version_text: str = "unknown"
    manifold_args: list[str] = field(default_factory=list)
    summary_file: bool = False
    export_format: bool = False

    @property
    def backend(self) -> str:
        return "manifold" if self.manifold_args else "cgal"


@dataclass
class MeshResult:
    """A rendered mesh (STL) plus what OpenSCAD said while making it."""

    ok: bool
    stl: Path | None
    returncode: int
    output: str
    diagnostics: dict[str, Any]
    cached: bool = False
    dimension: int | None = None
    summary: dict[str, Any] | None = None


@dataclass
class _Flight:
    """An in-progress render shared by every caller asking for the same mesh."""

    task: asyncio.Future
    waiters: int = 0


def candidate_binaries() -> list[str]:
    """Every plausible OpenSCAD executable on this system, de-duplicated."""
    found: list[str] = []
    which = shutil.which("openscad")
    if which:
        found.append(which)
    patterns = [
        "/Applications/OpenSCAD*.app/Contents/MacOS/OpenSCAD",
        str(Path.home() / "Applications/OpenSCAD*.app/Contents/MacOS/OpenSCAD"),
        "/usr/bin/openscad",
        "/usr/local/bin/openscad",
        "/snap/bin/openscad",
        r"C:\Program Files\OpenSCAD*\openscad.exe",
    ]
    for pat in patterns:
        found.extend(sorted(glob.glob(pat)))
    seen: set[str] = set()
    out = []
    for p in found:
        real = os.path.realpath(p)
        if real not in seen and os.path.isfile(p) and os.access(p, os.X_OK):
            seen.add(real)
            out.append(p)
    return out


def _probe_version(binary: str, flag: str = "--version") -> str:
    try:
        r = subprocess.run([binary, flag], capture_output=True, text=True, timeout=15)
        return (r.stderr + r.stdout).strip()
    except (OSError, subprocess.SubprocessError):
        return ""


class OpenSCADClient:
    """Manages OpenSCAD CLI invocations."""

    def __init__(
        self,
        workspace: Path | None = None,
        libraries: Path | None = None,
        cache_dir: Path | None = None,
        jobs: int | None = None,
    ) -> None:
        self.workspace = workspace or DEFAULT_WORKSPACE
        self.libraries = libraries or DEFAULT_LIBRARIES
        self.cache_dir = cache_dir or DEFAULT_CACHE
        self.binary: str | None = None
        self.features = Features()
        self._jobs = jobs or int(os.environ.get("OPENSCAD_MCP_JOBS", "0")) or max(1, (os.cpu_count() or 2) - 1)
        self._sem: asyncio.Semaphore | None = None
        self._probed = False
        self._probe_retry_at = 0.0
        self._ready_lock = threading.Lock()
        self._flights: dict[str, _Flight] = {}
        self._procs: set[asyncio.subprocess.Process] = set()
        self._last_sweep = 0.0

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover_binary(self) -> str:
        """Find OpenSCAD: $OPENSCAD_BINARY first, else the newest install."""
        env = os.environ.get("OPENSCAD_BINARY")
        if env:
            if os.path.isfile(env):
                return env
            raise FileNotFoundError(f"OPENSCAD_BINARY points to a missing file: {env}")
        cands = candidate_binaries()
        if not cands:
            raise FileNotFoundError(
                "OpenSCAD binary not found. Install from https://openscad.org/ "
                "or ensure 'openscad' is on your PATH (or set OPENSCAD_BINARY)."
            )
        if len(cands) == 1:
            return cands[0]
        # Prefer the newest version; ties keep PATH order.
        return max(cands, key=lambda b: parse_version(_probe_version(b)))

    def probe_features(self) -> Features | None:
        """Ask the binary for its version and options (both at once), or None
        when it answered neither, so the probe is repeated later."""
        assert self.binary
        with ThreadPoolExecutor(2) as pool:
            version_job = pool.submit(_probe_version, self.binary, "--version")
            help_job = pool.submit(_probe_version, self.binary, "--help")
            version_text, help_text = version_job.result(), help_job.result()
        if not (version_text or help_text):
            return None
        manifold: list[str] = []
        if "--backend" in help_text:
            manifold = ["--backend=manifold"]
        elif re.search(r"--enable.*manifold", help_text, re.S):
            manifold = ["--enable=manifold"]
        if os.environ.get("OPENSCAD_MCP_BACKEND", "").lower() == "cgal":
            manifold = []
        return Features(
            version=parse_version(version_text),
            version_text=version_text or "unknown",
            manifold_args=manifold,
            summary_file="--summary-file" in help_text,
            export_format="--export-format" in help_text,
        )

    def ensure_ready(self) -> None:
        """Verify binary exists, probe its features and create directories.

        Safe to call from the startup thread and from tool calls at once. A
        binary that does not answer the probe is asked again after
        PROBE_RETRY_S instead of being treated as featureless for the session.
        """
        with self._ready_lock:
            if self.binary is None:
                self.binary = self.discover_binary()
            if not self._probed and time.monotonic() >= self._probe_retry_at:
                features = self.probe_features()
                if features is None:
                    self._probe_retry_at = time.monotonic() + PROBE_RETRY_S
                    logger.warning("OpenSCAD did not answer --version/--help; will probe again")
                else:
                    self.features = features
                    self._probed = True
            self.workspace.mkdir(parents=True, exist_ok=True)
            try:
                self.libraries.mkdir(parents=True, exist_ok=True)
            except OSError:
                logger.debug("Could not create the libraries folder %s", self.libraries)
            self._sync_library_symlinks()

    def _sync_library_symlinks(self) -> None:
        """Create symlinks in workspace for each installed library."""
        if not self.libraries.is_dir():
            return
        for lib_dir in self.libraries.iterdir():
            if lib_dir.is_dir() and not lib_dir.name.startswith("."):
                link = self.workspace / lib_dir.name
                if not link.exists() and not link.is_symlink():
                    try:
                        link.symlink_to(lib_dir)
                        logger.info("Symlinked library: %s", lib_dir.name)
                    except OSError:
                        logger.debug("Could not symlink %s", lib_dir.name)

    def bundled_library_dir(self) -> Path | None:
        """The libraries folder shipped inside the OpenSCAD install (MCAD)."""
        if not self.binary:
            return None
        real = Path(os.path.realpath(self.binary))
        for cand in (
            real.parent.parent / "Resources" / "libraries",  # macOS bundle
            real.parent.parent / "share" / "openscad" / "libraries",  # Linux prefix
            real.parent / "libraries",  # Windows
        ):
            if cand.is_dir():
                return cand
        return None

    def library_paths(self) -> list[str]:
        """Directories put on OPENSCADPATH for every run."""
        paths = []
        if self.libraries.is_dir():
            paths.append(str(self.libraries))
        bundled = self.bundled_library_dir()
        if bundled and str(bundled) not in paths:
            paths.append(str(bundled))
        return paths

    # ------------------------------------------------------------------
    # Core runner
    # ------------------------------------------------------------------

    async def run(
        self,
        args: list[str],
        timeout: float | None = None,
    ) -> tuple[int, str, str]:
        """Run openscad with the given arguments; returns (rc, stdout, stderr).

        Concurrency is capped (OPENSCAD_MCP_JOBS) so parallel renders do not
        thrash the machine. CGAL cache chatter is removed from stderr.
        """
        if self.binary is None or not self._probed:
            self.ensure_ready()
        timeout = timeout or RENDER_TIMEOUT
        cmd = [self.binary, *args]
        logger.debug("Running: %s", " ".join(map(str, cmd)))

        env = os.environ.copy()
        lib_paths = self.library_paths()
        if lib_paths:
            existing = env.get("OPENSCADPATH", "")
            env["OPENSCADPATH"] = os.pathsep.join(lib_paths + ([existing] if existing else []))

        if self._sem is None:
            self._sem = asyncio.Semaphore(self._jobs)
        async with self._sem:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace),
                env=env,
            )
            self._procs.add(proc)
            try:
                stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                await _kill(proc)
                raise TimeoutError(
                    f"OpenSCAD timed out after {timeout:g}s. Simplify the model, lower $fn, "
                    "or pass a larger timeout (OPENSCAD_MCP_TIMEOUT sets the default)."
                )
            except BaseException:
                # Cancelled request or client gone: never leave a render running.
                await _kill(proc)
                raise
            finally:
                self._procs.discard(proc)

        stdout = stdout_b.decode(errors="replace")
        stderr = stderr_b.decode(errors="replace")
        stderr = "\n".join(ln for ln in stderr.splitlines() if not ln.startswith("CGAL Cache"))
        return proc.returncode, stdout, stderr

    def kill_children(self) -> None:
        """Kill every OpenSCAD process still running (the server is being terminated)."""
        for proc in list(self._procs):
            if proc.returncode is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    logger.debug("OpenSCAD process already exited")

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------

    def resolve_path(self, filename: str) -> Path:
        """Resolve a filename relative to the workspace; refuse escapes.

        Containment is checked on whole path components, so a sibling such as
        `<workspace>-evil/x` is rejected too.
        """
        if "\x00" in filename:
            raise ValueError("Path traversal not allowed: NUL byte in filename")
        root = self.workspace.resolve()
        path = (root / filename).resolve()
        if path != root and not path.is_relative_to(root):
            raise ValueError(f"Path traversal not allowed: {filename}")
        return path

    def scratch_dir(self) -> Path:
        d = self.cache_dir / "scratch"
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ------------------------------------------------------------------
    # Mesh rendering with a dependency-aware cache
    # ------------------------------------------------------------------

    def _cache_key(self, src: Path, parameters: dict[str, Any] | None, extra: list[str]) -> str:
        blob = json.dumps(
            [
                self.binary,
                self.features.version_text,
                str(src),
                sorted(diagnostics.define_args(parameters)[1::2]),  # "name=value", order-free
                self.features.manifold_args,
                extra,
                # The search path decides which library file an include resolves to.
                self.library_paths(),
                os.environ.get("OPENSCADPATH", ""),
            ],
            sort_keys=True,
        )
        return hashlib.sha256(blob.encode()).hexdigest()[:32]

    @staticmethod
    def _digest(paths: list[str]) -> dict[str, str]:
        out = {}
        for p in paths:
            try:
                out[p] = hashlib.sha256(Path(p).read_bytes()).hexdigest()
            except OSError:
                out[p] = "missing"
        return out

    def _parse_deps(self, deps_file: Path) -> list[str]:
        try:
            text = deps_file.read_text(errors="replace")
        except OSError:
            return []
        _, _, body = text.partition(":")
        body = body.replace("\\\n", " ")
        parts = re.split(r"(?<!\\)\s+", body.strip())
        out = []
        for p in parts:
            if not p:
                continue
            p = p.replace("\\ ", " ")
            path = Path(p) if os.path.isabs(p) else self.workspace / p
            out.append(str(path.resolve()))
        return sorted(set(out))

    def _cached_mesh(self, key: str) -> MeshResult | None:
        """The cache entry for `key` if every recorded dependency is unchanged.

        An entry is meta.json naming its own mesh.<tag>.stl, which is never
        rewritten, so a path handed out stays valid while later renders of the
        same model publish new files.
        """
        entry = self.cache_dir / "mesh" / key
        meta_file = entry / "meta.json"
        try:
            meta = json.loads(meta_file.read_text())
            stl = entry / meta["stl"]
            if not (stl.is_file() and meta.get("deps")) or self._digest(list(meta["deps"])) != meta["deps"]:
                return None
        except FileNotFoundError:
            return None
        except (OSError, ValueError, KeyError, TypeError):
            # Unreadable, corrupt or old-layout entry: render afresh.
            logger.debug("Ignoring unusable cache entry %s", entry)
            return None
        try:
            os.utime(meta_file)  # last use, for eviction
        except OSError:
            logger.debug("Could not touch %s", meta_file)
        return MeshResult(True, stl, 0, meta.get("output", ""), meta.get("diagnostics", {}),
                          cached=True, dimension=3, summary=meta.get("summary"))

    async def render_mesh(
        self,
        src: Path,
        parameters: dict[str, Any] | None = None,
        timeout: float | None = None,
        use_cache: bool = True,
        extra_args: list[str] | None = None,
    ) -> MeshResult:
        """Render `src` (absolute path) to a binary STL, reusing the cache when
        neither the file nor anything it includes/imports has changed.

        Concurrent calls for the same model and parameters share one render
        (the first caller's timeout applies to it).
        """
        extra = list(extra_args or [])
        key = self._cache_key(src, parameters, extra)
        if not use_cache:
            return await self._render_mesh(key, src, parameters, timeout, extra)
        hit = self._cached_mesh(key)
        if hit is not None:
            return hit
        # The source digest keeps a call made after an edit from joining a
        # render of the previous text.
        name = f"{key}:{self._digest([str(src)])[str(src)]}"
        return await self._single_flight(name, lambda: self._render_mesh(key, src, parameters, timeout, extra))

    async def _single_flight(self, name: str, factory) -> MeshResult:
        flight = self._flights.get(name)
        if flight is None or flight.task.done():  # a finished (or cancelled) render is not joined
            flight = self._flights[name] = _Flight(asyncio.ensure_future(factory()))

            def done(task: asyncio.Future, name: str = name, flight: _Flight = flight) -> None:
                if self._flights.get(name) is flight:
                    del self._flights[name]
                if not task.cancelled():
                    task.exception()  # retrieved here so a render nobody awaits any more is not logged

            flight.task.add_done_callback(done)
        flight.waiters += 1
        try:
            return await asyncio.shield(flight.task)
        finally:
            flight.waiters -= 1
            if flight.waiters == 0 and not flight.task.done():
                # Every caller went away (cancelled requests): stop the render.
                flight.task.cancel()

    async def _render_mesh(
        self, key: str, src: Path, parameters: dict[str, Any] | None, timeout: float | None, extra: list[str]
    ) -> MeshResult:
        entry = self.cache_dir / "mesh" / key
        entry.mkdir(parents=True, exist_ok=True)
        tag = secrets.token_hex(6)
        stl = entry / f"mesh.{tag}.stl"
        deps_file = entry / f"deps.{tag}.mk"
        summary_file = entry / f"summary.{tag}.json"
        args = ["-o", str(stl), "-d", str(deps_file)]
        if self.features.export_format:
            args += ["--export-format", "binstl"]
        if self.features.summary_file:
            args += ["--summary-file", str(summary_file)]
        args += self.features.manifold_args + diagnostics.define_args(parameters) + extra + [str(src)]
        started = time.time()
        keep = False
        try:
            rc, stdout, stderr = await self.run(args, timeout=timeout)
            output = diagnostics.strip_noise(stderr + stdout)
            diag = diagnostics.parse_output(stderr + stdout)
            dimension = diag["stats"].get("dimension")
            if "not a 3D object" in stderr:
                dimension = 2
            ok = rc == 0 and stl.is_file() and not diag["errors"]
            if not ok:
                return MeshResult(False, None, rc, output, diag, dimension=dimension)
            summary = None
            if summary_file.is_file():
                try:
                    summary = json.loads(summary_file.read_text(errors="replace"))
                except ValueError:
                    summary = None
            deps = self._parse_deps(deps_file) or [str(src)]
            # Not cacheable when the dependency list is incomplete (a missing
            # include/use is only a warning and is absent from the -d output) or
            # a dependency changed while OpenSCAD was reading it.
            unresolved = any(
                w["message"].startswith(("Can't open include file", "Can't open library"))
                for w in diag["warnings"]
            )
            # Digest first, then look for edits: a file saved after OpenSCAD read it
            # has mtime >= started and blocks caching; one saved after the digest
            # only makes the stored digest older than the file (a miss next time).
            digests = self._digest(deps)
            changed = any(_mtime(p) >= started for p in deps)
            keep = True  # the caller reads this STL; unpublished ones are swept later
            if not (unresolved or changed):
                meta = {"stl": stl.name, "deps": digests, "output": output, "diagnostics": diag,
                        "source": str(src), "summary": summary}
                tmp_meta = entry / f"meta.{tag}.tmp"
                tmp_meta.write_text(json.dumps(meta))
                os.replace(tmp_meta, entry / "meta.json")
                self._maybe_sweep(keep=entry)
            return MeshResult(True, stl, rc, output, diag, cached=False, dimension=3, summary=summary)
        finally:
            if not keep:
                stl.unlink(missing_ok=True)
            deps_file.unlink(missing_ok=True)
            summary_file.unlink(missing_ok=True)

    def _maybe_sweep(self, keep: Path | None = None) -> None:
        now = time.monotonic()
        if now - self._last_sweep >= SWEEP_EVERY_S:
            self._last_sweep = now
            try:
                self.evict(keep=keep)
            except OSError:
                logger.debug("Cache sweep failed", exc_info=True)

    def evict(self, keep: Path | None = None, max_bytes: float | None = None,
              idle_s: float = 600.0) -> dict[str, Any]:
        """Keep the cache under OPENSCAD_MCP_CACHE_MAX_MB (default 512).

        Meshes no entry refers to any more (replaced, or from renders that could
        not be cached) and leftovers of interrupted renders go after an hour;
        then whole entries go, least recently used first. Entries used within
        `idle_s` seconds, and `keep`, are never removed, so paths just handed
        out stay valid. Scratch wrappers unused for a day are removed too.
        """
        limit = CACHE_MAX_MB * 1e6 if max_bytes is None else max_bytes
        now = time.time()
        entries: list[tuple[float, int, Path]] = []
        total = 0
        root = self.cache_dir / "mesh"
        for d in (os.scandir(root) if root.is_dir() else ()):
            if not d.is_dir(follow_symlinks=False):
                continue
            entry = Path(d.path)
            try:
                live = json.loads((entry / "meta.json").read_text()).get("stl")
                last = (entry / "meta.json").stat().st_mtime
            except (OSError, ValueError, AttributeError):
                live, last = None, 0.0
            size = 0
            for f in os.scandir(entry):
                try:
                    st = f.stat(follow_symlinks=False)
                except OSError:
                    continue
                if f.name not in ("meta.json", live) and now - st.st_mtime > 3600:
                    Path(f.path).unlink(missing_ok=True)
                else:
                    size += st.st_size
            entries.append((last, size, entry))
            total += size
        removed = 0
        for last, size, entry in sorted(entries, key=lambda e: e[0]):
            if total <= limit:
                break
            if entry == keep or now - last < idle_s:
                continue
            shutil.rmtree(entry, ignore_errors=True)
            total -= size
            removed += 1
        scratch = self.cache_dir / "scratch"
        for f in (os.scandir(scratch) if scratch.is_dir() else ()):
            try:
                if f.is_file(follow_symlinks=False) and now - f.stat().st_mtime > 86400:
                    Path(f.path).unlink(missing_ok=True)
            except OSError:
                continue
        return {"entries_removed": removed, "cache_bytes": total, "limit_bytes": int(limit)}

    def clear_cache(self) -> dict[str, Any]:
        """Remove only what this server owns (mesh/ and scratch/) under cache_dir."""
        freed = 0
        files = 0
        for sub in ("mesh", "scratch"):
            d = self.cache_dir / sub
            if d.is_dir() and not d.is_symlink():
                for p in d.rglob("*"):
                    if p.is_file():
                        freed += p.stat().st_size
                        files += 1
                shutil.rmtree(d, ignore_errors=True)
        return {"files_removed": files, "bytes_freed": freed, "cache_dir": str(self.cache_dir)}

    def write_wrapper(self, code: str) -> Path:
        """Write generated OpenSCAD code to a content-addressed scratch file."""
        name = hashlib.sha256(code.encode()).hexdigest()[:24] + ".scad"
        path = self.scratch_dir() / name
        try:
            os.utime(path)  # in use again: keep it from the scratch sweep
        except FileNotFoundError:
            tmp = path.with_suffix(f".{secrets.token_hex(4)}.tmp")
            tmp.write_text(code, encoding="utf-8")
            os.replace(tmp, path)
        return path

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    async def version(self) -> str:
        """Return the OpenSCAD version string."""
        rc, stdout, stderr = await self.run(["--version"], timeout=15)
        text = (stderr + stdout).strip()
        return text or "unknown"

    async def export(
        self,
        scad_file: str,
        output_file: str,
        parameters: dict[str, Any] | None = None,
        extra_args: list[str] | None = None,
        timeout: float | None = None,
    ) -> tuple[int, str, str]:
        """Export a .scad file to the format given by the output extension."""
        src = self.resolve_path(scad_file)
        dst = self.resolve_path(output_file)
        dst.parent.mkdir(parents=True, exist_ok=True)
        args = ["-o", str(dst)]
        if dst.suffix.lower() == ".stl" and self.features.export_format:
            args += ["--export-format", "binstl"]
        args += self.features.manifold_args + diagnostics.define_args(parameters)
        if extra_args:
            args.extend(extra_args)
        args.append(str(src))
        return await self.run(args, timeout=timeout)

    async def preview(
        self,
        scad_file: str,
        output_png: str,
        imgsize: tuple[int, int] = (1024, 768),
        camera: str | None = None,
        colorscheme: str | None = None,
        projection: str | None = None,
        extra_args: list[str] | None = None,
        parameters: dict[str, Any] | None = None,
        timeout: float | None = None,
        src_path: Path | None = None,
    ) -> tuple[int, str, str]:
        """Render a PNG preview of a .scad file."""
        src = src_path or self.resolve_path(scad_file)
        dst = self.resolve_path(output_png)
        dst.parent.mkdir(parents=True, exist_ok=True)
        # Extra options go first: on 2021.01 "--render" takes an optional value and
        # would swallow the input path if it came last.
        args = ["-o", str(dst), *(extra_args or []),
                "--imgsize", f"{imgsize[0]},{imgsize[1]}", "--autocenter", "--viewall"]
        if camera:
            args.extend(["--camera", camera])
        if colorscheme:
            args.extend(["--colorscheme", colorscheme])
        if projection:
            args.extend(["--projection", projection])
        args += diagnostics.define_args(parameters)
        args.append(str(src))
        return await self.run(args, timeout=timeout)

    async def check_syntax(
        self, scad_file: str, parameters: dict[str, Any] | None = None
    ) -> tuple[int, str, str]:
        """Parse and evaluate a .scad file without building geometry."""
        src = self.resolve_path(scad_file)
        # Echo export evaluates without a CGAL render. OpenSCAD writes parser
        # errors and warnings into the .echo file, not stderr.
        with tempfile.TemporaryDirectory() as tmp:
            echo_file = Path(tmp) / "check.echo"
            rc, stdout, stderr = await self.run(
                ["-o", str(echo_file), *diagnostics.define_args(parameters), str(src)], timeout=60
            )
            if echo_file.exists():
                stderr = echo_file.read_text(errors="replace") + stderr
        return rc, stdout, stderr

    async def evaluate(
        self, scad_file: str | None, expressions: list[str], parameters: dict[str, Any] | None = None
    ) -> tuple[list[dict[str, Any]], str]:
        """Evaluate expressions (optionally in a model's scope) via echo()."""
        lines = []
        if scad_file:
            src = self.resolve_path(scad_file)
            if not src.is_file():
                raise ValueError(f"File not found: {scad_file}")
            if ">" in str(src):
                raise ValueError("File path must not contain '>'")
            lines.append(f"include <{src}>")
        # A per-call nonce keeps model output (or string values containing
        # newlines) from impersonating a result line.
        nonce = secrets.token_hex(4)
        for i, expr in enumerate(expressions):
            _check_expression(expr)
            lines.append(f"echo(__mcp_{nonce}_{i} = ({expr}));")
        wrapper = self.write_wrapper("\n".join(lines) + "\n")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                echo_file = Path(tmp) / "eval.echo"
                rc, stdout, stderr = await self.run(
                    ["-o", str(echo_file), *diagnostics.define_args(parameters), str(wrapper)], timeout=60
                )
                text = (echo_file.read_text(errors="replace") if echo_file.exists() else "") + stderr
        finally:
            wrapper.unlink(missing_ok=True)
        values: dict[int, str] = {}
        for m in re.finditer(rf"^ECHO: __mcp_{nonce}_(\d+) = (.*)$", text, re.M):
            values.setdefault(int(m.group(1)), m.group(2).strip())
        text = re.sub(rf"__mcp_{nonce}_(\d+)", r"expr\1", text)
        results = []
        for i, expr in enumerate(expressions):
            raw = values.get(i)
            results.append({"expression": expr, "value": raw, "type": _value_type(raw)})
        return results, text

    async def render_animated(
        self,
        scad_file: str,
        output_prefix: str,
        num_frames: int,
        imgsize: tuple[int, int] = (800, 600),
        extra_args: list[str] | None = None,
        timeout: float | None = None,
    ) -> tuple[int, str, str]:
        """Render animation frames <prefix>NNNNN.png with $t = i / num_frames.

        Each frame is its own OpenSCAD run (in parallel, up to the job limit)
        instead of `--animate`, which crashes under Xvfb on OpenSCAD 2021
        (X BadLength after a few frames) and renders frames one at a time.
        Returns (rc, stdout, stderr) of the first failing frame, else the last.
        """
        src = self.resolve_path(scad_file)
        dst = self.resolve_path(output_prefix)
        dst.parent.mkdir(parents=True, exist_ok=True)
        stem = dst.with_suffix("")

        async def frame(i: int) -> tuple[int, str, str]:
            args = [
                "-o", f"{stem}{i:05d}.png",
                "--imgsize", f"{imgsize[0]},{imgsize[1]}",
                "--autocenter",
                "--viewall",
                "-D", f"$t={i / num_frames!r}",
                *(extra_args or []),
                str(src),
            ]
            return await self.run(args, timeout=timeout)

        results = await asyncio.gather(*(frame(i) for i in range(num_frames)))
        for res in results:
            if res[0] != 0:
                return res
        return results[-1]


async def _kill(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is None:
        try:
            proc.kill()
        except ProcessLookupError:
            # The process exited between the returncode check and kill(); nothing to stop.
            logger.debug("OpenSCAD process already exited")
        await proc.wait()


def _mtime(path: str) -> float:
    try:
        return os.stat(path).st_mtime
    except OSError:
        return float("inf")  # vanished during the render: do not trust the result


def _check_expression(expr: str) -> None:
    """One self-contained expression: no statements, balanced brackets."""
    if ";" in expr or "\n" in expr or "\r" in expr:
        raise ValueError(f"Expression must be a single expression without ';' or newlines: {expr!r}")
    depth = {"(": 0, "[": 0, "{": 0}
    close = {")": "(", "]": "[", "}": "{"}
    in_str = False
    i = 0
    while i < len(expr):
        c = expr[i]
        if in_str:
            if c == "\\":
                i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c in depth:
            depth[c] += 1
        elif c in close:
            depth[close[c]] -= 1
            if depth[close[c]] < 0:
                raise ValueError(f"Unbalanced brackets in expression: {expr!r}")
        i += 1
    if in_str or any(depth.values()):
        raise ValueError(f"Unbalanced brackets or quotes in expression: {expr!r}")


def _value_type(raw: str | None) -> str:
    if raw is None:
        return "missing"
    if raw == "undef":
        return "undef"
    if raw in ("true", "false"):
        return "bool"
    if raw.startswith('"'):
        return "string"
    if raw.startswith("["):
        return "range" if re.match(r"^\[[^,\[\]]+:[^\[\]]+\]$", raw) else "vector"
    try:
        float(raw)
        return "number"
    except ValueError:
        return "other"
