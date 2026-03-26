#!/usr/bin/env python3
"""
git_sync.py — Auto commit + push uncommitted changes to new-architecture.

Usage:
  python3 scripts/git_sync.py [--message "commit msg"] [--dry-run]

Rules:
  - Only pushes to origin/new-architecture (hard-coded, never master)
  - Skips if no changes
  - Skips if sanity check fails (syntax errors in core/*.py / scripts/*.py)
  - Reports exact error on push failure
  - Does NOT embed tokens in URL — relies on gh auth git-credential
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
BRANCH = "new-architecture"
REMOTE = "origin"

SANITY_TARGETS = [
    "core/router.py",
    "core/execution_pipeline.py",
    "core/agent_executor.py",
    "core/model_selector.py",
    "core/action_executor.py",
    "scripts/orchestrator.py",
]


def run(cmd: list[str], cwd=WORKSPACE, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)


def has_changes() -> bool:
    result = run(["git", "status", "--short"])
    return bool(result.stdout.strip())


def sanity_check() -> tuple[bool, str]:
    """Compile-check critical Python files. Returns (ok, error_msg)."""
    for rel in SANITY_TARGETS:
        path = WORKSPACE / rel
        if not path.exists():
            continue
        result = run(
            [sys.executable, "-m", "py_compile", str(path)],
            check=False
        )
        if result.returncode != 0:
            return False, f"Syntax error in {rel}: {result.stderr.strip()}"
    return True, ""


def current_branch() -> str:
    return run(["git", "branch", "--show-current"]).stdout.strip()


def sync(commit_message: str = "", dry_run: bool = False) -> dict:
    result = {"status": "unknown", "changes": False, "commit": "", "push": ""}

    # 1. Check for changes
    if not has_changes():
        result["status"] = "no_changes"
        return result
    result["changes"] = True

    # 2. Sanity check
    ok, err = sanity_check()
    if not ok:
        result["status"] = "sanity_failed"
        result["error"] = err
        return result

    # 3. Verify branch
    branch = current_branch()
    if branch != BRANCH:
        result["status"] = "wrong_branch"
        result["error"] = f"Expected {BRANCH}, got {branch}"
        return result

    if not commit_message:
        commit_message = f"auto: sync workspace changes {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    if dry_run:
        result["status"] = "dry_run"
        result["would_commit"] = commit_message
        return result

    # 4. Commit
    run(["git", "add", "-A"])
    commit = run(["git", "commit", "-m", commit_message], check=False)
    if commit.returncode != 0:
        result["status"] = "commit_failed"
        result["error"] = commit.stderr.strip()
        return result
    result["commit"] = run(["git", "rev-parse", "--short", "HEAD"]).stdout.strip()

    # 5. Push
    push = run(["git", "push", REMOTE, BRANCH], check=False)
    if push.returncode != 0:
        result["status"] = "push_failed"
        result["error"] = push.stderr.strip()
        return result

    result["status"] = "ok"
    result["push"] = f"{REMOTE}/{BRANCH}"
    return result


def main():
    parser = argparse.ArgumentParser(description="Auto git sync to new-architecture")
    parser.add_argument("--message", "-m", default="", help="Commit message")
    parser.add_argument("--dry-run", action="store_true", help="Check only, don't commit/push")
    args = parser.parse_args()

    r = sync(commit_message=args.message, dry_run=args.dry_run)

    status = r["status"]
    if status == "no_changes":
        print("✅ No changes — nothing to push")
    elif status == "ok":
        print(f"✅ Pushed {r['commit']} → {r['push']}")
    elif status == "dry_run":
        print(f"🔍 Dry run — would commit: {r['would_commit']}")
    elif status == "sanity_failed":
        print(f"❌ Sanity failed: {r['error']}", file=sys.stderr)
        sys.exit(1)
    elif status == "wrong_branch":
        print(f"❌ Wrong branch: {r['error']}", file=sys.stderr)
        sys.exit(1)
    elif status == "push_failed":
        print(f"❌ Push failed: {r['error']}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"❌ {status}: {r.get('error','')}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
