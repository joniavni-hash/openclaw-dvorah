#!/usr/bin/env bash
# git_audit.sh — quick repo health snapshot
# Usage: bash scripts/git_audit.sh [--full]

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

FULL=${1:-""}

echo "========================================="
echo "  Git Audit — $(date '+%Y-%m-%d %H:%M %Z')"
echo "  Branch: $(git branch --show-current)"
echo "========================================="
echo ""

# ── 1. Recent commits ─────────────────────────
echo "📋 Last 10 commits:"
git log --oneline -10
echo ""

# ── 2. Uncommitted changes ────────────────────
DIRTY=$(git status --porcelain)
if [ -n "$DIRTY" ]; then
  echo "⚠️  Uncommitted changes:"
  git status --short
else
  echo "✅ Working tree clean"
fi
echo ""

# ── 3. Unpushed commits ───────────────────────
UPSTREAM=$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || echo "")
if [ -n "$UPSTREAM" ]; then
  UNPUSHED=$(git log "@{u}..HEAD" --oneline 2>/dev/null)
  if [ -n "$UNPUSHED" ]; then
    echo "📤 Unpushed commits (vs $UPSTREAM):"
    echo "$UNPUSHED"
  else
    echo "✅ In sync with $UPSTREAM"
  fi
else
  echo "ℹ️  No upstream tracking branch set"
fi
echo ""

# ── 4. File counts by type ────────────────────
echo "📂 Tracked files by type:"
git ls-files | grep -oE '\.[^./]+$' | sort | uniq -c | sort -rn | head -15
echo ""

# ── 5. Large files ────────────────────────────
echo "🔍 Largest tracked files (top 10):"
git ls-files | xargs -I{} du -sh {} 2>/dev/null | sort -rh | head -10
echo ""

# ── 6. Branches ───────────────────────────────
echo "🌿 Branches:"
git branch -a --sort=-committerdate | head -10
echo ""

# ── 7. Stashes ────────────────────────────────
STASHES=$(git stash list 2>/dev/null)
if [ -n "$STASHES" ]; then
  echo "📦 Stashes:"
  echo "$STASHES"
  echo ""
fi

# ── 8. Secrets scan (basic) ───────────────────
echo "🔐 Secrets scan (basic):"
SECRETS_FOUND=0
PATTERNS=("password\s*=" "api_key\s*=" "secret\s*=" "token\s*=" "private_key")
for pat in "${PATTERNS[@]}"; do
  HITS=$(git grep -il "$pat" -- '*.py' '*.json' '*.yaml' '*.yml' '*.env' 2>/dev/null \
         | grep -v "__pycache__\|\.git\|secrets/\.env\|test\|spec\|example" || true)
  if [ -n "$HITS" ]; then
    echo "  ⚠️  Pattern '$pat' found in:"
    echo "$HITS" | sed 's/^/    /'
    SECRETS_FOUND=1
  fi
done
[ "$SECRETS_FOUND" -eq 0 ] && echo "  ✅ No obvious secrets found in tracked files"
echo ""

# ── 9. Full diff stat (optional) ──────────────
if [ "$FULL" = "--full" ]; then
  echo "📊 Full diff stat (HEAD~10..HEAD):"
  git diff --stat HEAD~10..HEAD 2>/dev/null || echo "  (not enough history)"
  echo ""
fi

echo "========================================="
echo "  Audit complete."
echo "========================================="
