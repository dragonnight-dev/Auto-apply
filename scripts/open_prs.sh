#!/usr/bin/env bash
# Pushes the daily branches and opens one pull request per day. Each PR targets the previous
# day's branch, so each shows only that day's commits. Merge them oldest first.
# Needs a git remote named origin, and the GitHub CLI signed in (gh auth login).
set -euo pipefail

base=main
git push -u origin main
for branch in $(git for-each-ref --format='%(refname:short)' --sort=refname refs/heads/day/); do
  git push -u origin "$branch"
  body="$(git log --reverse --format='- %s' "$base..$branch")"
  gh pr create --base "$base" --head "$branch" --title "Work from ${branch#day/}" \
    --body "$body"$'\n\n'"🤖 Generated with [Claude Code](https://claude.com/claude-code)"
  base="$branch"
done
