#!/usr/bin/env python3
"""Add CWE fields to rules/asvs-v<N>-rules.yml from cwe.xml.

For every rule whose ASVS id appears in scripts/asvs-5.0.0-cwe-mapping.yml, a
`cwe:` block is inserted after the `rule:` line, matching the fields of
Weakness_Catalog/Weaknesses/Weakness in cwe.xml:

    cwe:
      id: 306                      # Weakness@ID
      name: "..."                  # Weakness@Name
      abstraction: "Base"          # Weakness@Abstraction (or "Category")
      url: "https://cwe.mitre.org/data/definitions/306.html"
      note: "..."                  # Common_Consequences/Consequence/Note (joined)

scripts/cwe.xml (override with $CWE_XML) is the CWE-699 view from
https://cwe.mitre.org/data/downloads.html and is not committed. Some mapped
CWEs (class-level weaknesses and categories) are not in that view. Pass the full MITRE catalog with
--catalog to resolve those; otherwise only id and url are written for them.

The script is idempotent: existing `cwe:` blocks are replaced. It edits the
files textually so the generator's layout and quoting are preserved.

Usage:
    enrich-rules-with-cwe.py [--catalog cwec_vX.Y.xml ...] [--quiet]
"""
import argparse
import glob
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.environ.get("SKILL_DIR") or os.path.join(os.path.dirname(SCRIPT_DIR), "skills", "asvs")
RULES_DIR = os.path.join(SKILL_DIR, "rules")
MAPPING = os.path.join(SCRIPT_DIR, "asvs-5.0.0-cwe-mapping.yml")
CWE_XML = os.environ.get("CWE_XML") or os.path.join(SCRIPT_DIR, "cwe.xml")
NS = {"c": "http://cwe.mitre.org/cwe-7"}
URL = "https://cwe.mitre.org/data/definitions/{id}.html"


def q(s):
    """YAML double-quoted scalar (JSON escaping is a valid subset)."""
    return json.dumps(s, ensure_ascii=False)


def text_of(el):
    return " ".join("".join(el.itertext()).split())


def load_mapping(path):
    """Minimal parser for the flat list in asvs-5.0.0-cwe-mapping.yml."""
    m, cur = {}, None
    for line in open(path, encoding="utf-8"):
        s = line.strip()
        if s.startswith("- asvs:"):
            cur = s.split(":", 1)[1].strip().strip('"')
        elif s.startswith("cwe:") and cur:
            m[cur] = int(s.split(":", 1)[1].strip())
            cur = None
    return m


def load_catalog(path, entries, meta):
    root = ET.parse(path).getroot()
    meta.setdefault("versions", []).append(
        f"{os.path.basename(path)}: CWE {root.get('Version')} ({root.get('Date')}), {root.get('Name')}"
    )
    for w in root.findall("c:Weaknesses/c:Weakness", NS):
        wid = int(w.get("ID"))
        if wid in entries:
            continue
        notes = [text_of(n) for n in w.findall("c:Common_Consequences/c:Consequence/c:Note", NS)]
        notes = [n for n in notes if n]
        entries[wid] = {
            "id": wid,
            "name": w.get("Name"),
            "abstraction": w.get("Abstraction"),
            "note": "\n\n".join(dict.fromkeys(notes)) if notes else None,
        }
    for c in root.findall("c:Categories/c:Category", NS):
        cid = int(c.get("ID"))
        if cid not in entries:
            entries[cid] = {"id": cid, "name": c.get("Name"), "abstraction": "Category", "note": None}


def cwe_block(cwe, entries):
    e = entries.get(cwe)
    lines = ["    cwe:", f"      id: {cwe}"]
    if e:
        lines.append(f"      name: {q(e['name'])}")
        lines.append(f"      abstraction: {q(e['abstraction'])}")
    lines.append(f"      url: {q(URL.format(id=cwe))}")
    if e and e["note"]:
        lines.append(f"      note: {q(e['note'])}")
    return lines


def meta_block(meta, mapped, unresolved):
    lines = ["  cwe:", f"    mapped: {mapped}"]
    if unresolved:
        lines.append(f"    unresolved: {unresolved}")
    lines.append("    mapping: \"scripts/asvs-5.0.0-cwe-mapping.yml (derived from OWASP ASVS 5.0.be, indicative only)\"")
    lines.append("    catalogs:")
    for v in meta["versions"]:
        lines.append(f"      - {q(v)}")
    return lines


def strip_indented(lines, i, indent):
    """Skip lines after index i that are indented more than `indent` spaces."""
    while i < len(lines) and lines[i].startswith(" " * (indent + 1)) and lines[i].strip():
        i += 1
    return i


def process(path, mapping, entries, meta):
    src = open(path, encoding="utf-8").read().splitlines()
    out, i, mapped, unresolved, rule_id = [], 0, 0, 0, None
    # First pass: count so the meta block can be written before the rules.
    ids = [re.match(r'  - id: "ASVS-V\d+-([\d.]+)"', l) for l in src]
    ids = [m.group(1) for m in ids if m]
    mapped = sum(1 for x in ids if x in mapping)
    unresolved = sum(1 for x in ids if x in mapping and mapping[x] not in entries)
    while i < len(src):
        line = src[i]
        if line.startswith("  cwe:") and not line.startswith("    "):      # old meta block
            i = strip_indented(src, i + 1, 2)
            continue
        if line.startswith("    cwe:"):                                       # old rule block
            i = strip_indented(src, i + 1, 4)
            continue
        m = re.match(r'  - id: "ASVS-V\d+-([\d.]+)"', line)
        if m:
            rule_id = m.group(1)
        out.append(line)
        if line.startswith("  per_level:"):
            out.extend(meta_block(meta, mapped, unresolved))
        elif line.startswith("    rule:") and rule_id in mapping:
            out.extend(cwe_block(mapping[rule_id], entries))
        i += 1
    open(path, "w", encoding="utf-8").write("\n".join(out) + "\n")
    return len(ids), mapped, unresolved


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--catalog", action="append", default=[], help="extra CWE XML catalog(s) used as fallback")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    if not os.path.isfile(CWE_XML):
        sys.exit(f"error: {CWE_XML} not found; download the CWE-699 view (XML) from "
                 "https://cwe.mitre.org/data/downloads.html or set CWE_XML")
    mapping = load_mapping(MAPPING)
    entries, meta = {}, {}
    for cat in [CWE_XML] + a.catalog:
        load_catalog(cat, entries, meta)

    missing = sorted({c for c in mapping.values() if c not in entries})
    tot = (0, 0, 0)
    for path in sorted(glob.glob(os.path.join(RULES_DIR, "asvs-v*-rules.yml")),
                       key=lambda p: int(re.search(r"v(\d+)-", p).group(1))):
        n, m, u = process(path, mapping, entries, meta)
        tot = tuple(x + y for x, y in zip(tot, (n, m, u)))
        if not a.quiet:
            print(f"{os.path.basename(path)}: {m}/{n} rules mapped to CWE" + (f", {u} unresolved" if u else ""))
    print(f"total: {tot[1]}/{tot[0]} rules mapped, {tot[2]} unresolved")
    if missing:
        print(f"warning: {len(missing)} CWE ids not in the loaded catalog(s): "
              + ", ".join(map(str, missing)), file=sys.stderr)
        print("hint: pass --catalog <cwec_vX.Y.xml> (full catalog from https://cwe.mitre.org/data/downloads.html)",
              file=sys.stderr)


if __name__ == "__main__":
    main()
