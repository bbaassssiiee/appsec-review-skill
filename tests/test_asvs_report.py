"""Tests for skills/appsec-review/scripts/asvs-report.py."""
import json
import os
import re
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(REPO, "skills", "appsec-review")
SCRIPT = os.path.join(SKILL, "scripts", "asvs-report.py")
CHECKLIST = os.path.join(SKILL, "assets", "design-review-checklist.md")
SCHEMA = os.path.join(SKILL, "assets", "report-schema.json")


def run(*args):
    proc = subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def good():
    return {
        "scope": "src/auth",
        "level": 2,
        "inventory": ["web UI + REST API", "password login"],
        "chapters": ["V6", "V7"],
        "skipped_chapters": {"V17": "no WebRTC"},
        "sections_na": {"V6.6": "no out-of-band authentication"},
        "findings": [
            {"id": "6.2.1", "status": "FAIL", "evidence": "`auth/password.py:42` minimum length is 6",
             "remediation": "Raise the minimum to 8."},
            {"id": "v5.0.0-7.2.1", "status": "PASS", "evidence": "`session.ts:18` validated server side"},
            {"id": "ASVS-V6-6.1.1", "status": "UNVERIFIED", "reason": "no documentation in scope"},
            {"id": "6.4.1", "status": "N/A", "reason": "no credential recovery"},
        ],
        "top_risks": ["Short passwords accepted (6.2.1)"],
        "missing_evidence": ["Authentication documentation"],
    }


@pytest.fixture
def findings(tmp_path):
    def write(doc):
        p = tmp_path / "findings.json"
        p.write_text(json.dumps(doc), encoding="utf-8")
        return str(p)
    return write


def test_example_is_valid(tmp_path):
    code, out, _ = run("--example")
    assert code == 0
    p = tmp_path / "example.json"
    p.write_text(out, encoding="utf-8")
    code, out, err = run(str(p), "--validate")
    assert code == 0, err
    assert "OK" in out


def test_markdown_report(findings):
    code, out, err = run(findings(good()))
    assert code == 0, err
    assert out.startswith("💂🏼 ASVS 5.0.0 verification: src/auth, target L2\n")
    assert "Inventory: web UI + REST API, password login" in out
    assert "Chapters: V6, V7 (skipped: V17 no WebRTC)" in out
    assert "Sections N/A: V6.6 (no out-of-band authentication)" in out
    # rows are sorted by id and ids are in standard notation, with level and CWE filled in
    rows = [line for line in out.splitlines() if line.startswith("| v5.0.0-")]
    assert [r.split(" | ")[0] for r in rows] == ["| v5.0.0-6.1.1", "| v5.0.0-6.2.1", "| v5.0.0-6.4.1", "| v5.0.0-7.2.1"]
    assert "| v5.0.0-6.2.1 | 1 | FAIL | `auth/password.py:42` minimum length is 6 | [CWE-521](https://cwe.mitre.org/data/definitions/521.html) |" in out
    assert "Summary: 1 PASS, 1 FAIL, 0 PARTIAL, 1 N/A, 1 UNVERIFIED" in out
    assert "Remediation\n- v5.0.0-6.2.1 (FAIL): Raise the minimum to 8." in out
    assert "Top risks\n1. Short passwords accepted (6.2.1)" in out
    assert "Missing evidence\n- Authentication documentation" in out


def test_writes_output_file(findings, tmp_path):
    out_file = tmp_path / "report.md"
    code, out, _ = run(findings(good()), "-o", str(out_file))
    assert code == 0
    assert "wrote" in out
    assert out_file.read_text(encoding="utf-8").startswith("💂🏼")


def test_json_format_adds_summary_and_expands(findings):
    code, out, _ = run(findings(good()), "--format", "json")
    assert code == 0
    doc = json.loads(out)
    assert doc["summary"] == {"PASS": 1, "FAIL": 1, "PARTIAL": 0, "N/A": 1, "UNVERIFIED": 1}
    f = {x["id"]: x for x in doc["findings"]}
    assert f["v5.0.0-6.2.1"]["level"] == 1
    assert f["v5.0.0-6.2.1"]["cwe"] == "CWE-521"
    assert f["v5.0.0-6.2.1"]["section"] == "V6.2"
    assert f["v5.0.0-6.2.1"]["rule"].startswith("User set passwords")


@pytest.mark.parametrize("mutate, message", [
    (lambda d: d["findings"].append({"id": "6.9.9", "status": "PASS", "evidence": "x"}), "unknown requirement"),
    (lambda d: d["findings"].append({"id": "6.2.1", "status": "PASS", "evidence": "x"}), "duplicate requirement"),
    (lambda d: d["findings"][0].update(status="MAYBE"), "status must be one of"),
    (lambda d: d["findings"][0].pop("remediation"), "FAIL needs a remediation"),
    (lambda d: d["findings"][1].pop("evidence"), "PASS needs evidence"),
    (lambda d: d["findings"][3].pop("reason"), "N/A needs a reason"),
    (lambda d: d["findings"].append({"id": "6.3.5", "status": "PASS", "evidence": "x"}), "L3 rule in an L2 review"),
    (lambda d: d.update(level=4), "level must be 1, 2 or 3"),
    (lambda d: d.pop("scope"), "scope is required"),
    (lambda d: d.update(findings=[]), "findings must be a non-empty list"),
])
def test_validation_errors(findings, mutate, message):
    doc = good()
    mutate(doc)
    code, out, err = run(findings(doc), "--validate")
    assert code == 1
    assert out == ""
    assert message in err


def test_invalid_json_is_reported(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    code, _, err = run(str(p))
    assert code == 1
    assert "not valid JSON" in err


def test_schema_file_is_json_and_matches_statuses():
    with open(SCHEMA, encoding="utf-8") as fh:
        schema = json.load(fh)
    statuses = schema["properties"]["findings"]["items"]["properties"]["status"]["enum"]
    assert statuses == ["PASS", "FAIL", "PARTIAL", "N/A", "UNVERIFIED"]


def test_checklist_ids_exist_and_levels_match():
    import importlib.util
    spec = importlib.util.spec_from_file_location("asvs_rules", os.path.join(SKILL, "scripts", "asvs-rules.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _, rules = mod.load()
    index = {mod.short_id(r["id"]): r for r in rules}
    checked = 0
    with open(CHECKLIST, encoding="utf-8") as fh:
        for line in fh:
            ids = re.findall(r"\[(\d+\.\d+\.\d+)\]", line)
            if not ids:
                continue
            m = re.search(r"\((L[23])\)", line)
            level = int(m.group(1)[1]) if m else 1
            for i in ids:
                assert i in index, f"unknown id {i} in checklist"
                assert index[i]["level"] == level, f"{i}: checklist says L{level}, rule is L{index[i]['level']}"
                checked += 1
    assert checked >= 30
