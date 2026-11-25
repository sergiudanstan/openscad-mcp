# Contributing

Contributions are welcome. This is a single-maintainer project, so please open an issue
before starting anything substantial.

**Security problems do not belong in issues.** Follow [SECURITY.md](SECURITY.md).

## Branches, pull requests and releases

- `main` is the only long-lived branch and is protected: changes land through a pull
  request with the required checks green, commits on `main` are signed, and force-pushes
  are refused. Pull requests are squash-merged; GitHub deletes the branch on merge.
- Branch names: `<type>/<topic>` (`feat/`, `fix/`, `docs/`, `chore/`, `release/`);
  agents use `agent/<name>/<topic>`.
- A release is a pull request that bumps `version` in `pyproject.toml` (and the matching entry in `uv.lock`, via `uv lock`) and moves
  `[Unreleased]` in [CHANGELOG.md](CHANGELOG.md) to a dated version. After it merges, a
  signed `vX.Y.Z` tag on that commit triggers `release.yml`, which refuses to run if the
  tag, the declared version and the changelog disagree. Tags are never moved or deleted.

## Running it locally

```bash
uv sync --locked --extra dev      # or: pip install -e ".[dev]"
uv run pytest -q tests            # needs the openscad CLI on PATH; set REQUIRE_OPENSCAD=1 to fail instead of skip
uv run python -m openscad_mcp     # run the server over stdio
```

Tests that run the real CLI are skipped when `openscad` is not installed; CI installs it and sets `REQUIRE_OPENSCAD=1`. After changing dependencies, run `uv lock` and commit `uv.lock`; CI installs with `--locked`.
