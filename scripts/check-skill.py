#!/usr/bin/env python3
"""Validate skills/*/SKILL.md against the Agent Skills format.

Checks per skill:
  - frontmatter present with `name` and `description`
  - name: 1-64 chars, lowercase letters, digits and hyphens, equal to the folder name
  - description: 1-1024 chars
  - every backticked or linked path under rules/, references/ or scripts/ exists
    (paths with placeholders such as <N> or * are skipped)

Usage:
    check-skill.py [skills/<name>/SKILL.md ...]   # default: all skills
"""
import glob
import os
import re
import sys

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
PATH_RE = re.compile(r"(?:`|\]\()((?:rules|references|scripts)/[^`)\s]+)")
PLACEHOLDER = re.compile(r"[<>*?]")


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    fields = {}
    for line in m.group(1).splitlines():
        k, sep, v = line.partition(":")
        if sep and not line.startswith(" "):
            fields[k.strip()] = v.strip().strip('"').strip("'")
    return fields


def check(path):
    errors = []
    skill_dir = os.path.dirname(path)
    text = open(path, encoding="utf-8").read()
    fm = frontmatter(text)
    if fm is None:
        return [f"{path}: missing YAML frontmatter"]

    name = fm.get("name", "")
    if not NAME_RE.match(name) or len(name) > 64:
        errors.append(f"{path}: invalid name {name!r}")
    if name != os.path.basename(skill_dir):
        errors.append(f"{path}: name {name!r} does not match folder {os.path.basename(skill_dir)!r}")

    desc = fm.get("description", "")
    if not 1 <= len(desc) <= 1024:
        errors.append(f"{path}: description must be 1-1024 chars (is {len(desc)})")

    for ref in sorted({r for r in PATH_RE.findall(text) if not PLACEHOLDER.search(r)}):
        if not os.path.exists(os.path.join(skill_dir, ref)):
            errors.append(f"{path}: referenced file not found: {ref}")
    return errors


def main():
    paths = sys.argv[1:] or sorted(glob.glob(os.path.join(REPO_DIR, "skills", "*", "SKILL.md")))
    if not paths:
        sys.exit("error: no skills/*/SKILL.md found")
    errors = [e for p in paths for e in check(p)]
    for e in errors:
        print(e, file=sys.stderr)
    if errors:
        sys.exit(1)
    print(f"OK: {len(paths)} skill(s) valid")


if __name__ == "__main__":
    main()
