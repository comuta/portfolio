"""Content versioning via a local git repo with no remote (FA-41).

The content directory is its own git repository, entirely separate from
this application's repository. The admin app commits after every write;
history/diff/revert then come from git itself, not custom code.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def ensure_repo(content_dir: Path) -> None:
    if (content_dir / ".git").is_dir():
        return
    content_dir.mkdir(parents=True, exist_ok=True)
    _run(content_dir, ["init"])
    _run(content_dir, ["config", "user.email", "admin@portfolio.local"])
    _run(content_dir, ["config", "user.name", "Portfolio Admin"])


def commit_all(content_dir: Path, message: str) -> None:
    """Stage everything and commit, if anything actually changed."""
    ensure_repo(content_dir)
    _run(content_dir, ["add", "-A"])

    nothing_staged = _run(content_dir, ["diff", "--cached", "--quiet"], check=False).returncode == 0
    if nothing_staged:
        return

    _run(content_dir, ["commit", "-m", message])


def _run(content_dir: Path, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    # Bind-mounted content dirs routinely end up owned by a different uid than
    # the one git sees itself running as (root creates it in the `init`
    # container, a chown follows, host<->container uid mapping on Docker
    # Desktop adds another layer) — git's "dubious ownership" check (safe by
    # default for a shared multi-user machine) would otherwise refuse every
    # command here. Scoping trust to exactly this one app-controlled path,
    # per invocation, is safe: there's no other user on this container whose
    # repo we could be tricked into trusting.
    result = subprocess.run(
        ["git", "-c", f"safe.directory={content_dir}", "-C", str(content_dir), *args],
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        logger.error("git %s failed: %s", args, result.stderr.strip())
        result.check_returncode()
    return result
