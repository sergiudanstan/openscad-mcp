"""Subprocess wrapper for the OpenSCAD CLI."""

import asyncio
import logging
import os
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_WORKSPACE = Path.home() / "openscad-mcp-workspace"
DEFAULT_LIBRARIES = Path.home() / "Documents" / "OpenSCAD" / "libraries"
RENDER_TIMEOUT = 60  # seconds


class OpenSCADClient:
    """Manages OpenSCAD CLI invocations."""

    def __init__(self, workspace: Path | None = None) -> None:
        self.workspace = workspace or DEFAULT_WORKSPACE
        self.libraries = DEFAULT_LIBRARIES
        self.binary: str | None = None

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover_binary(self) -> str:
        """Find the openscad binary on this system."""
        # 1. PATH lookup
        found = shutil.which("openscad")
        if found:
            return found

        # 2. macOS app bundle
        mac_path = "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"
        if os.path.isfile(mac_path):
            return mac_path

        raise FileNotFoundError(
            "OpenSCAD binary not found. Install from https://openscad.org/ "
            "or ensure 'openscad' is on your PATH."
        )

    def ensure_ready(self) -> None:
        """Verify binary exists and workspace directory is created."""
        if self.binary is None:
            self.binary = self.discover_binary()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.libraries.mkdir(parents=True, exist_ok=True)
        # Symlink each library into workspace so use<Lib/file.scad> works
        self._sync_library_symlinks()

    def _sync_library_symlinks(self) -> None:
        """Create symlinks in workspace for each installed library."""
        if not self.libraries.is_dir():
            return
        for lib_dir in self.libraries.iterdir():
            if lib_dir.is_dir() and not lib_dir.name.startswith("."):
                link = self.workspace / lib_dir.name
                if not link.exists():
                    try:
                        link.symlink_to(lib_dir)
                        logger.info("Symlinked library: %s", lib_dir.name)
                    except OSError:
                        logger.debug("Could not symlink %s", lib_dir.name)

    def library_paths(self) -> list[str]:
        """Return --library flags for all installed library directories."""
        paths = []
        if self.libraries.is_dir():
            paths.append(str(self.libraries))
        # Also add MCAD from the app bundle if present
        mcad_path = Path("/Applications/OpenSCAD-2021.01.app/Contents/Resources/libraries")
        if mcad_path.is_dir() and str(mcad_path) not in paths:
            paths.append(str(mcad_path))
        return paths

    # ------------------------------------------------------------------
    # Core runner
    # ------------------------------------------------------------------

    async def run(
        self,
        args: list[str],
        timeout: float = RENDER_TIMEOUT,
    ) -> tuple[int, str, str]:
        """Run openscad with the given arguments.

        Automatically sets OPENSCADPATH so all installed libraries are found.
        Returns (returncode, stdout, stderr).
        """
        cmd = [self.binary, *args]
        logger.debug("Running: %s", " ".join(cmd))

        # Build environment with OPENSCADPATH pointing to all library dirs
        env = os.environ.copy()
        lib_paths = self.library_paths()
        if lib_paths:
            existing = env.get("OPENSCADPATH", "")
            all_paths = lib_paths + ([existing] if existing else [])
            env["OPENSCADPATH"] = os.pathsep.join(all_paths)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.workspace),
            env=env,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise TimeoutError(
                f"OpenSCAD timed out after {timeout}s. "
                "Try simplifying the model or increasing timeout."
            )

        stdout = stdout_b.decode(errors="replace")
        stderr = stderr_b.decode(errors="replace")
        return proc.returncode, stdout, stderr

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def resolve_path(self, filename: str) -> Path:
        """Resolve a filename relative to the workspace.

        Prevents path traversal outside workspace.
        """
        path = (self.workspace / filename).resolve()
        if not str(path).startswith(str(self.workspace.resolve())):
            raise ValueError(f"Path traversal not allowed: {filename}")
        return path

    async def version(self) -> str:
        """Return the OpenSCAD version string."""
        rc, stdout, stderr = await self.run(["--version"], timeout=10)
        # OpenSCAD prints version to stderr
        text = (stderr + stdout).strip()
        return text or "unknown"

    async def export(
        self,
        scad_file: str,
        output_file: str,
        parameters: dict[str, str] | None = None,
        extra_args: list[str] | None = None,
    ) -> tuple[int, str, str]:
        """Export a .scad file to the given output format."""
        src = self.resolve_path(scad_file)
        dst = self.resolve_path(output_file)
        args = ["-o", str(dst)]
        if parameters:
            for k, v in parameters.items():
                args.extend(["-D", f"{k}={v}"])
        if extra_args:
            args.extend(extra_args)
        args.append(str(src))
        return await self.run(args)

    async def preview(
        self,
        scad_file: str,
        output_png: str,
        imgsize: tuple[int, int] = (1024, 768),
        camera: str | None = None,
        colorscheme: str | None = None,
        projection: str | None = None,
        extra_args: list[str] | None = None,
    ) -> tuple[int, str, str]:
        """Render a PNG preview of a .scad file."""
        src = self.resolve_path(scad_file)
        dst = self.resolve_path(output_png)
        args = [
            "-o", str(dst),
            "--imgsize", f"{imgsize[0]},{imgsize[1]}",
            "--autocenter",
            "--viewall",
        ]
        if camera:
            args.extend(["--camera", camera])
        if colorscheme:
            args.extend(["--colorscheme", colorscheme])
        if projection:
            args.extend(["--projection", projection])
        if extra_args:
            args.extend(extra_args)
        args.append(str(src))
        return await self.run(args)

    async def check_syntax(self, scad_file: str) -> tuple[int, str, str]:
        """Dry-run a .scad file to check for syntax errors."""
        src = self.resolve_path(scad_file)
        # Export to /dev/null (or nul on Windows) to trigger parse without render
        null = "/dev/null" if os.name != "nt" else "NUL"
        args = ["-o", null, str(src)]
        return await self.run(args, timeout=15)

    async def render_animated(
        self,
        scad_file: str,
        output_prefix: str,
        num_frames: int,
        imgsize: tuple[int, int] = (800, 600),
        extra_args: list[str] | None = None,
    ) -> tuple[int, str, str]:
        """Render animation frames using the $t variable."""
        src = self.resolve_path(scad_file)
        dst = self.resolve_path(output_prefix)
        args = [
            "-o", str(dst),
            "--imgsize", f"{imgsize[0]},{imgsize[1]}",
            "--animate", str(num_frames),
            "--autocenter",
            "--viewall",
        ]
        if extra_args:
            args.extend(extra_args)
        args.append(str(src))
        return await self.run(args, timeout=num_frames * 5)

    async def get_info(
        self, scad_file: str, summary_file: str
    ) -> tuple[int, str, str]:
        """Run with --summary-file to get render statistics."""
        src = self.resolve_path(scad_file)
        summary = self.resolve_path(summary_file)
        null = "/dev/null" if os.name != "nt" else "NUL"
        args = ["-o", null, "--summary-file", str(summary), str(src)]
        return await self.run(args)
