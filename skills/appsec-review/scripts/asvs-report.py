#!/usr/bin/env python3
"""Render an ASVS verification report from a findings file.

The agent records only what it decided (id, status, evidence, why,
remediation); this script adds the level, rule text, CWE link, name and
typical consequence from the rules files, checks that every id exists and
every status is valid, and computes the summary counts, so the numbers in
the report are never typed by hand. PASS rows stay one table line; every
FAIL and PARTIAL gets a Findings entry that explains the requirement, what
was found, why it matters and how to fix it.

Usage:
    asvs-report.py findings.json                 # Markdown report on stdout
    asvs-report.py findings.json -o report.md    # write to a file
    asvs-report.py findings.json --validate      # check only, print problems, exit 1 on any
    asvs-report.py findings.json --format json   # normalised JSON (ids expanded, counts added)
    asvs-report.py --example                     # print an example findings file

Findings file (JSON; see ../assets/report-schema.json):
    {
      "scope": "src/auth, PR #42",
      "level": 2,
      "inventory": ["web UI + REST API", "password login with TOTP"],
      "chapters": ["V6", "V7"],
      "skipped_chapters": {"V17": "no WebRTC"},
      "sections_na": {"V6.6": "no out-of-band authentication"},
      "findings": [
        {"id": "6.2.1", "status": "FAIL",
         "evidence": "`auth/password.py:42` minimum length is 6",
         "why": "Six-character passwords fall to online guessing within the lockout budget, and offline cracking of the stored hashes is trivial.",
         "remediation": "Raise the minimum to 8 (15 recommended) in the validator and the signup form."},
        {"id": "7.2.1", "status": "PASS", "evidence": "`session.ts:18` tokens validated server side"}
      ],
      "top_risks": ["Weak password policy lets short passwords through (6.2.1)"],
      "missing_evidence": ["No tests for session expiry; needed for 7.3.1"]
    }
"""
import argparse
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STATUSES = ("PASS", "FAIL", "PARTIAL", "N/A", "UNVERIFIED")
CWE_URL = "https://cwe.mitre.org/data/definitions/{}.html"
EXAMPLE = __doc__.split("Findings file (JSON; see ../assets/report-schema.json):", 1)[1]


def _rules_module():
    spec = importlib.util.spec_from_file_location("asvs_rules", os.path.join(HERE, "asvs-rules.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_rules():
    mod = _rules_module()
    _, rules = mod.load()
    return mod, {mod.short_id(r["id"]): r for r in rules}


# --- validation ----------------------------------------------------------------

def validate(doc, rules, norm_id):
    problems = []
    if not isinstance(doc, dict):
        return ["findings file must be a JSON object"]
    if doc.get("level") not in (1, 2, 3):
        problems.append("level must be 1, 2 or 3")
    if not doc.get("scope"):
        problems.append("scope is required")
    for key in ("inventory", "chapters", "top_risks", "missing_evidence"):
        if key in doc and not isinstance(doc[key], list):
            problems.append(f"{key} must be a list")
    for key in ("skipped_chapters", "sections_na"):
        if key in doc and not isinstance(doc[key], dict):
            problems.append(f"{key} must be an object of id -> reason")
    findings = doc.get("findings")
    if not isinstance(findings, list) or not findings:
        problems.append("findings must be a non-empty list")
        return problems
    seen = set()
    for i, f in enumerate(findings):
        where = f"findings[{i}]"
        if not isinstance(f, dict) or "id" not in f:
            problems.append(f"{where}: needs an id")
            continue
        sid = norm_id(str(f["id"]))
        if sid not in rules:
            problems.append(f"{where}: unknown requirement {f['id']!r}")
            continue
        if sid in seen:
            problems.append(f"{where}: duplicate requirement {sid}")
        seen.add(sid)
        status = f.get("status")
        if status not in STATUSES:
            problems.append(f"{where} ({sid}): status must be one of {', '.join(STATUSES)}")
        if status in ("PASS", "FAIL", "PARTIAL") and not f.get("evidence"):
            problems.append(f"{where} ({sid}): {status} needs evidence")
        if status == "N/A" and not (f.get("evidence") or f.get("reason")):
            problems.append(f"{where} ({sid}): N/A needs a reason")
        if status in ("FAIL", "PARTIAL") and not f.get("remediation"):
            problems.append(f"{where} ({sid}): {status} needs a remediation")
        if doc.get("level") in (1, 2, 3) and rules[sid]["level"] > doc["level"]:
            problems.append(f"{where} ({sid}): L{rules[sid]['level']} rule in an L{doc['level']} review")
    return problems


# --- rendering -----------------------------------------------------------------

def cwe_link(rule):
    c = rule.get("cwe")
    if not c or not c.get("id"):
        return ""
    return f"[CWE-{c['id']}]({CWE_URL.format(c['id'])})"


def expand(doc, rules, norm_id, std_id):
    out = []
    for f in doc["findings"]:
        sid = norm_id(str(f["id"]))
        r = rules[sid]
        out.append({
            "id": std_id(r["id"]),
            "chapter": r["chapter"],
            "section": r["section"],
            "level": r["level"],
            "status": f["status"],
            "evidence": f.get("evidence") or f.get("reason") or "",
            "remediation": f.get("remediation", ""),
            "rule": r["rule"],
            "cwe": f"CWE-{r['cwe']['id']}" if r.get("cwe") and r["cwe"].get("id") else "",
            "cwe_link": cwe_link(r),
            "cwe_name": (r.get("cwe") or {}).get("name", ""),
            "cwe_note": (r.get("cwe") or {}).get("note", ""),
            "why": f.get("why", ""),
        })
    out.sort(key=lambda x: [int(p) for p in x["id"].split("-", 1)[1].split(".")])
    return out


def counts(expanded):
    c = {s: 0 for s in STATUSES}
    for f in expanded:
        c[f["status"]] += 1
    return c


def render_markdown(doc, expanded):
    lines = [f"💂🏼 ASVS 5.0.0 verification: {doc['scope']}, target L{doc['level']}"]
    if doc.get("inventory"):
        lines.append("Inventory: " + ", ".join(doc["inventory"]))
    chapters = doc.get("chapters") or sorted({f["chapter"] for f in expanded}, key=lambda c: int(c[1:]))
    skipped = doc.get("skipped_chapters") or {}
    line = "Chapters: " + ", ".join(chapters)
    if skipped:
        line += " (skipped: " + "; ".join(f"{k} {v}" for k, v in skipped.items()) + ")"
    lines.append(line)
    na = doc.get("sections_na") or {}
    if na:
        lines.append("Sections N/A: " + ", ".join(f"{k} ({v})" for k, v in na.items()))
    lines += ["", "| Requirement | L | Status | Evidence / finding | CWE |", "|---|---|---|---|---|"]
    for f in expanded:
        ev = f["evidence"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {f['id']} | {f['level']} | {f['status']} | {ev} | {f['cwe_link']} |")
    c = counts(expanded)
    lines += ["", "Summary: " + ", ".join(f"{c[s]} {s}" for s in STATUSES)]
    risks = doc.get("top_risks") or []
    if risks:
        lines += ["", "Top risks"] + [f"{i}. {r}" for i, r in enumerate(risks, 1)]
    fixes = sorted((f for f in expanded if f["status"] in ("FAIL", "PARTIAL")),
                   key=lambda f: (f["level"], [int(p) for p in f["id"].split("-", 1)[1].split(".")]))
    if fixes:
        lines += ["", "Findings"]
        for f in fixes:
            lines += ["", f"### {f['id']} {f['status']} (L{f['level']})",
                      f"Requirement: {f['rule']}",
                      f"Found: {f['evidence']}"]
            why = f["why"]
            if f["cwe"]:
                weakness = f"{f['cwe_link']} {f['cwe_name']}".strip()
                if f["cwe_note"]:
                    weakness += f": {f['cwe_note']}"
                lines.append(f"Why it matters: {weakness}" + (f" {why}" if why else ""))
            elif why:
                lines.append(f"Why it matters: {why}")
            lines.append(f"Fix: {f['remediation']}")
    missing = doc.get("missing_evidence") or []
    if missing:
        lines += ["", "Missing evidence"] + [f"- {m}" for m in missing]
    return "\n".join(lines) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=__doc__.split("Usage:", 1)[1])
    p.add_argument("findings", nargs="?", help="findings JSON file")
    p.add_argument("-o", "--output", help="write the report here instead of stdout")
    p.add_argument("--format", choices=("markdown", "json"), default="markdown")
    p.add_argument("--validate", action="store_true", help="only check the findings file")
    p.add_argument("--example", action="store_true", help="print an example findings file")
    args = p.parse_args(argv)

    if args.example:
        print(EXAMPLE.strip())
        return 0
    if not args.findings:
        p.error("a findings file is required")
    with open(args.findings, encoding="utf-8") as fh:
        try:
            doc = json.load(fh)
        except json.JSONDecodeError as e:
            print(f"error: {args.findings} is not valid JSON: {e}", file=sys.stderr)
            return 1

    mod, rules = load_rules()
    problems = validate(doc, rules, mod.norm_id)
    if problems:
        for pr in problems:
            print(f"error: {pr}", file=sys.stderr)
        return 1
    if args.validate:
        print(f"OK: {len(doc['findings'])} findings valid")
        return 0

    expanded = expand(doc, rules, mod.norm_id, mod.std_id)
    if args.format == "json":
        out = dict(doc, findings=expanded, summary=counts(expanded))
        text = json.dumps(out, indent=1, ensure_ascii=False) + "\n"
    else:
        text = render_markdown(doc, expanded)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"wrote {args.output}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
