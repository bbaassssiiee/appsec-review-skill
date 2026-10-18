#!/usr/bin/env python3
"""Query the ASVS rules without loading whole chapters into context.

Prints only the requirements that match the filters, in a compact form.
Run it from anywhere; it finds `rules/` relative to this script.

Usage:
    asvs-rules.py [filters] [--format table|ids|sections|json] [--with-cwe]

Filters (combine freely; all must match):
    --chapter V6 V7 ...     chapter(s), "V6" or "6"
    --level 2               maximum level: keep rules with level <= N (default: all)
    --exact-level 1         keep only rules at exactly this level
    --section V6.2 ...      section id(s)
    --id 6.2.1 ...          requirement id(s): "6.2.1", "v5.0.0-6.2.1" or "ASVS-V6-6.2.1"
    --keyword jwt ...       case-insensitive substring of the rule text (any keyword matches)

Output formats:
    table      id | level | rule text (default)
    ids        id and the first ~80 characters, one per line, grouped by section
    sections   per section: id, title and rule count per level - for triage
    json       full rule objects

Examples:
    asvs-rules.py --chapter V6 --format sections          # what is in V6, before reading rules
    asvs-rules.py --chapter V6 --level 2 --format ids     # every L1+L2 id in V6, one line each
    asvs-rules.py --section V6.2 V6.3 --level 2           # the full text of two sections
    asvs-rules.py --keyword jwt token --level 2           # across all chapters
    asvs-rules.py --id 6.2.1 6.2.2 --with-cwe             # specific requirements, with CWE
"""
import argparse
import glob
import json
import os
import re
import sys

RULES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "rules")
STANDARD_PREFIX = "v5.0.0-"


# --- loading ---------------------------------------------------------------

def _parse_minimal(text):
    """Parse the rules file format without PyYAML.

    The generated files use a fixed layout (two-space indent, double-quoted
    strings, integer levels), which is all this parser understands.
    """
    meta = {"sections": []}
    rules = []
    cur = None
    cwe = None
    in_meta = True
    for line in text.splitlines():
        if line.startswith("rules:"):
            in_meta = False
            continue
        m = re.match(r'^(\s*)(- )?([A-Za-z_]+):\s*(.*)$', line)
        if not m:
            continue
        indent, dash, key, raw = m.groups()
        val = _scalar(raw)
        if in_meta:
            if indent == "    " and dash and key == "id":
                meta["sections"].append({"id": val})
            elif indent == "      " and key == "title" and meta["sections"]:
                meta["sections"][-1]["title"] = val
            elif indent == "  " and key in ("chapter", "title", "standard"):
                meta[key] = val
            continue
        if dash and key == "id" and indent == "  ":
            cur = {"id": val}
            cwe = None
            rules.append(cur)
        elif cur is not None and indent == "    ":
            if key == "cwe":
                cwe = {}
                cur["cwe"] = cwe
            else:
                cur[key] = val
        elif cwe is not None and indent == "      ":
            cwe[key] = val
    return {"meta": meta, "rules": rules}


def _scalar(raw):
    raw = raw.strip()
    if raw == "":
        return None
    if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        return raw[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    return raw


def load_chapter(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text)
    except ImportError:
        data = _parse_minimal(text)
    meta = data.get("meta", {})
    rules = data.get("rules", [])
    for r in rules:
        r["chapter"] = meta.get("chapter")
    return meta, rules


def chapter_number(name):
    m = re.fullmatch(r"[Vv]?(\d{1,2})", str(name).strip())
    if not m:
        raise SystemExit(f"error: not a chapter: {name!r} (expected V1..V17)")
    return int(m.group(1))


def load(chapters=None):
    if chapters:
        paths = [os.path.join(RULES_DIR, f"asvs-v{chapter_number(c)}-rules.yml") for c in chapters]
    else:
        paths = sorted(glob.glob(os.path.join(RULES_DIR, "asvs-v*-rules.yml")),
                       key=lambda p: int(re.search(r"v(\d+)-rules", p).group(1)))
    metas, rules = [], []
    for p in paths:
        if not os.path.exists(p):
            raise SystemExit(f"error: no rules file {os.path.relpath(p)}")
        m, r = load_chapter(p)
        metas.append(m)
        rules.extend(r)
    return metas, rules


# --- filtering -------------------------------------------------------------

def short_id(rule_id):
    """'ASVS-V6-6.2.1' -> '6.2.1'"""
    return rule_id.rsplit("-", 1)[-1]


def std_id(rule_id):
    return STANDARD_PREFIX + short_id(rule_id)


def norm_id(s):
    s = s.strip()
    if s.startswith(STANDARD_PREFIX):
        s = s[len(STANDARD_PREFIX):]
    return short_id(s)


def select(rules, args):
    ids = {norm_id(i) for i in args.id} if args.id else None
    sections = {s.upper() for s in args.section} if args.section else None
    keywords = [k.lower() for k in args.keyword] if args.keyword else None
    out = []
    for r in rules:
        if args.level is not None and r["level"] > args.level:
            continue
        if args.exact_level is not None and r["level"] != args.exact_level:
            continue
        if sections and r["section"].upper() not in sections:
            continue
        if ids and short_id(r["id"]) not in ids:
            continue
        if keywords and not any(k in r["rule"].lower() for k in keywords):
            continue
        out.append(r)
    return out


# --- output ----------------------------------------------------------------

def cwe_text(r):
    c = r.get("cwe")
    return f"CWE-{c['id']}" if c and c.get("id") else ""


def fmt_table(rules, with_cwe):
    for r in rules:
        line = f"{std_id(r['id'])} | L{r['level']} | {r['rule']}"
        if with_cwe and cwe_text(r):
            line += f" | {cwe_text(r)}"
        print(line)


def fmt_ids(rules, with_cwe):
    last = None
    for r in rules:
        if r["section"] != last:
            print(f"[{r['section']}]")
            last = r["section"]
        text = r["rule"]
        text = text if len(text) <= 80 else text[:77].rstrip() + "..."
        line = f"  {std_id(r['id'])} L{r['level']} {text}"
        if with_cwe and cwe_text(r):
            line += f" ({cwe_text(r)})"
        print(line)


def fmt_sections(metas, rules):
    titles = {s["id"]: s.get("title", "") for m in metas for s in m.get("sections", [])}
    counts = {}
    for r in rules:
        counts.setdefault(r["section"], [0, 0, 0])[r["level"] - 1] += 1
    for m in metas:
        print(f"{m.get('chapter')} {m.get('title')}")
        for s in m.get("sections", []):
            c = counts.get(s["id"])
            if not c:
                continue
            print(f"  {s['id']:<6} L1:{c[0]:<3} L2:{c[1]:<3} L3:{c[2]:<3} {titles.get(s['id'], '')}")


def fmt_json(rules):
    print(json.dumps(rules, indent=1, ensure_ascii=False))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=__doc__.split("Usage:", 1)[1])
    p.add_argument("--chapter", nargs="+", metavar="V<N>")
    p.add_argument("--level", type=int, choices=(1, 2, 3))
    p.add_argument("--exact-level", type=int, choices=(1, 2, 3))
    p.add_argument("--section", nargs="+", metavar="V<N>.<M>")
    p.add_argument("--id", nargs="+", metavar="ID")
    p.add_argument("--keyword", nargs="+", metavar="WORD")
    p.add_argument("--format", choices=("table", "ids", "sections", "json"), default="table")
    p.add_argument("--with-cwe", action="store_true", help="append the CWE id (table, ids)")
    args = p.parse_args(argv)

    metas, rules = load(args.chapter)
    hits = select(rules, args)
    if args.format == "sections":
        fmt_sections(metas, hits)
    elif not hits:
        print("no requirements match these filters", file=sys.stderr)
        return 1
    elif args.format == "table":
        fmt_table(hits, args.with_cwe)
    elif args.format == "ids":
        fmt_ids(hits, args.with_cwe)
    else:
        fmt_json(hits)
    return 0


if __name__ == "__main__":
    sys.exit(main())
