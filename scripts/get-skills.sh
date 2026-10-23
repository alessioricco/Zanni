#!/usr/bin/env bash
# Download the agent skills listed in SKILLS.md, at the pinned commit, into the project's skills folder.
# Usage: scripts/get-skills.sh [--dir <folder>]    (default folder: the `dir:` line in SKILLS.md)
# Needs only curl and tar. Safe to re-run: each listed skill is replaced with the pinned version.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
manifest="$root/SKILLS.md"
[[ -f "$manifest" ]] || { echo "get-skills: $manifest not found" >&2; exit 1; }

# Read the ```skills block: `key: value` lines, then one skill name per line.
block="$(awk '/^```skills$/{on=1; next} /^```$/{on=0} on' "$manifest")"
field() { printf '%s\n' "$block" | sed -n "s/^$1:[[:space:]]*//p"; }
repo="$(field repo)"; commit="$(field commit)"; dir="$(field dir)"
skills=()
while IFS= read -r line; do skills+=("$line"); done < <(printf '%s\n' "$block" | grep -v ':' | grep -v '^[[:space:]]*$')

if [[ "${1:-}" == "--dir" && -n "${2:-}" ]]; then dir="$2"; fi
[[ -n "$repo" && -n "$commit" && -n "$dir" && ${#skills[@]} -gt 0 ]] \
  || { echo "get-skills: the skills block in SKILLS.md needs repo, commit, dir and at least one skill" >&2; exit 1; }
[[ "$commit" =~ ^[0-9a-f]{40}$ ]] || { echo "get-skills: commit must be a full 40-character SHA, got '$commit'" >&2; exit 1; }
for s in "${skills[@]}"; do
  [[ "$s" =~ ^[a-z0-9][a-z0-9-]*$ ]] || { echo "get-skills: '$s' is not a valid skill name" >&2; exit 1; }
done

case "$dir" in /*) target="$dir" ;; *) target="$root/$dir" ;; esac
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT

echo "Downloading $repo@${commit:0:12}..."
curl -fsSL "https://codeload.github.com/$repo/tar.gz/$commit" -o "$tmp/skills.tar.gz"
mkdir "$tmp/src"
tar -xzf "$tmp/skills.tar.gz" -C "$tmp/src" --strip-components 1

for s in "${skills[@]}"; do  # check every name before changing anything
  [[ -f "$tmp/src/skills/$s/SKILL.md" ]] || { echo "get-skills: no skill '$s' in $repo@${commit:0:12}" >&2; exit 1; }
done

mkdir -p "$target"
for s in "${skills[@]}"; do
  src="$tmp/src/skills/$s"
  rm -rf "${target:?}/$s"
  cp -R "$src" "$target/$s"
  printf '%s\n' "$repo@$commit skills/$s" > "$target/$s/.source"
  printf '# Downloaded by scripts/get-skills.sh; not part of this repository.\n*\n' > "$target/$s/.gitignore"
  echo "  $s -> ${target#"$root"/}/$s"
done
echo "Done: ${#skills[@]} skills."
