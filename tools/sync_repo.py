#!/usr/bin/env python3
"""
sync_repo.py — Sync local git repository with remote master branch.

Runs git fetch + pull when the local branch is behind the remote.
Designed to be called at the start of run_pipeline.sh so the server
always executes the latest code before the pipeline begins.

Usage:
    python3 tools/sync_repo.py [options]

Options:
    --repo-path PATH    Path to the git repository (default: project root)
    --branch BRANCH     Branch to sync (default: master)
    --remote REMOTE     Remote name (default: origin)
    --log-file PATH     Log file path (default: <repo>/logs/sync_repo.log)
    --dry-run           Fetch and compare only — do not pull

Exit codes:
    0  Already up-to-date or successfully synced
    1  Error (fetch failed, pull failed, not a git repo)
"""

import argparse
import logging
import os
import subprocess
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging(log_file: Path) -> logging.Logger:
    logger = logging.getLogger("sync_repo")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler (5 MB, 3 backups)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    fh = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def run_git(args: list, cwd: Path, logger: logging.Logger) -> subprocess.CompletedProcess:
    """Run a git command and return the result. Raises on non-zero exit."""
    cmd = ["git"] + args
    logger.debug("Running: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    return result


def get_sha(ref: str, cwd: Path, logger: logging.Logger) -> str:
    """Return the commit SHA for a given ref, or empty string on failure."""
    result = run_git(["rev-parse", ref], cwd, logger)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def short(sha: str) -> str:
    """Return the first 8 characters of a SHA."""
    return sha[:8] if sha else "unknown"


# ---------------------------------------------------------------------------
# Main sync logic
# ---------------------------------------------------------------------------

def sync(repo_path: Path, branch: str, remote: str, dry_run: bool, logger: logging.Logger) -> int:
    """
    Sync the repo. Returns 0 on success, 1 on error.
    """

    # Verify this is actually a git repo
    check = run_git(["rev-parse", "--git-dir"], repo_path, logger)
    if check.returncode != 0:
        logger.error("Not a git repository: %s", repo_path)
        return 1

    logger.info("Repository : %s", repo_path)
    logger.info("Remote     : %s", remote)
    logger.info("Branch     : %s", branch)

    # Step 1 — fetch
    logger.info("Fetching %s...", remote)
    fetch = run_git(["fetch", remote], repo_path, logger)
    if fetch.returncode != 0:
        logger.error("git fetch failed:\n%s", fetch.stderr.strip())
        return 1

    # Step 2 — compare SHAs
    local_sha  = get_sha("HEAD", repo_path, logger)
    remote_sha = get_sha(f"{remote}/{branch}", repo_path, logger)

    if not local_sha or not remote_sha:
        logger.error(
            "Could not resolve SHAs — local HEAD=%s, %s/%s=%s",
            local_sha, remote, branch, remote_sha,
        )
        return 1

    logger.info("Local  HEAD : %s", short(local_sha))
    logger.info("Remote HEAD : %s", short(remote_sha))

    if local_sha == remote_sha:
        logger.info("Already up-to-date — nothing to do")
        return 0

    # Step 3 — pull (unless dry-run)
    logger.info(
        "Changes detected: %s..%s",
        short(local_sha), short(remote_sha),
    )

    if dry_run:
        logger.info("[DRY-RUN] Would run: git pull %s %s", remote, branch)
        return 0

    logger.info("Pulling %s %s...", remote, branch)
    pull = run_git(["pull", remote, branch], repo_path, logger)
    if pull.returncode != 0:
        logger.error("git pull failed:\n%s", pull.stderr.strip())
        return 1

    new_sha = get_sha("HEAD", repo_path, logger)
    logger.info(
        "Sync complete: %s -> %s",
        short(local_sha), short(new_sha),
    )
    if pull.stdout.strip():
        logger.info(pull.stdout.strip())

    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    # Default repo path: two levels up from this script (tools/ -> project root)
    default_repo = Path(__file__).resolve().parent.parent

    parser = argparse.ArgumentParser(
        description="Sync local git repo with remote master before running the pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--repo-path", type=Path, default=default_repo,
        help=f"Path to the git repository (default: {default_repo})",
    )
    parser.add_argument(
        "--branch", default="master",
        help="Branch to sync (default: master)",
    )
    parser.add_argument(
        "--remote", default="origin",
        help="Remote name (default: origin)",
    )
    parser.add_argument(
        "--log-file", type=Path, default=None,
        help="Log file path (default: <repo>/logs/sync_repo.log)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Fetch and compare only — do not pull",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    repo_path = args.repo_path.resolve()
    log_file  = args.log_file or (repo_path / "logs" / "sync_repo.log")

    logger = setup_logging(log_file)

    if args.dry_run:
        logger.info("=== Git Sync (DRY-RUN) ===")
    else:
        logger.info("=== Git Sync ===")

    exit_code = sync(
        repo_path=repo_path,
        branch=args.branch,
        remote=args.remote,
        dry_run=args.dry_run,
        logger=logger,
    )

    if exit_code != 0:
        logger.error("Git sync failed — see above for details")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
