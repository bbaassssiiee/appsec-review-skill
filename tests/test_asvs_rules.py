"""Tests for skills/appsec-review/scripts/asvs-rules.py.

Run with `pytest` from the repository root. Only the standard library and
pytest are needed; the PyYAML comparison test is skipped when PyYAML is absent.
"""
import glob
import importlib.util
import json
import os
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(REPO, "skills", "appsec-review")
SCRIPT = os.path.join(SKILL, "scripts", "asvs-rules.py")
RULES = glob.glob(os.path.join(SKILL, "rules", "asvs-v*-rules.yml"))

spec = importlib.util.spec_from_file_location("asvs_rules", SCRIPT)
asvs_rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(asvs_rules)


def run(*args):
    proc = subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


# --- parser ------------------------------------------------------------------

def test_minimal_parser_reads_every_chapter():
    total = 0
    for path in RULES:
        with open(path, encoding="utf-8") as fh:
            data = asvs_rules._parse_minimal(fh.read())
        assert data["meta"]["chapter"].startswith("V")
        assert data["meta"]["sections"], path
        for r in data["rules"]:
            assert set(r) >= {"id", "section", "level", "rule"}, r
            assert r["level"] in (1, 2, 3)
            assert r["id"].startswith("ASVS-" + r["section"].split(".")[0] + "-")
        total += len(data["rules"])
    assert total == 345


def test_minimal_parser_matches_pyyaml():
    yaml = pytest.importorskip("yaml")
    for path in RULES:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        ref = yaml.safe_load(text)
        got = asvs_rules._parse_minimal(text)
        assert [s["id"] for s in ref["meta"]["sections"]] == [s["id"] for s in got["meta"]["sections"]]
        assert len(ref["rules"]) == len(got["rules"])
        for a, b in zip(ref["rules"], got["rules"]):
            for key in ("id", "section", "level", "rule"):
                assert a[key] == b[key], (path, a["id"], key)
            assert (a.get("cwe") or {}).get("id") == (b.get("cwe") or {}).get("id"), (path, a["id"])


def test_scalar_unescapes_quotes_and_backslashes():
    assert asvs_rules._scalar('"a \\"b\\" c"') == 'a "b" c'
    assert asvs_rules._scalar('"tab \\\\t"') == "tab \\t"
    assert asvs_rules._scalar("3") == 3
    assert asvs_rules._scalar("") is None


# --- id handling -------------------------------------------------------------

@pytest.mark.parametrize("given", ["6.2.1", "v5.0.0-6.2.1", "ASVS-V6-6.2.1"])
def test_id_forms_are_equivalent(given):
    assert asvs_rules.norm_id(given) == "6.2.1"


def test_chapter_number_accepts_v_prefix_or_bare():
    assert asvs_rules.chapter_number("V6") == 6
    assert asvs_rules.chapter_number("v17") == 17
    assert asvs_rules.chapter_number("3") == 3
    with pytest.raises(SystemExit):
        asvs_rules.chapter_number("six")


# --- cli ---------------------------------------------------------------------

def test_sections_format_lists_chapter_sections_with_counts():
    code, out, _ = run("--chapter", "V6", "--format", "sections")
    assert code == 0
    assert out.startswith("V6 Authentication")
    assert "V6.2" in out and "Password Security" in out
    assert "L1:8" in out  # V6.2 has eight L1 rules


def test_level_is_a_ceiling():
    code, out, _ = run("--chapter", "V6", "--level", "1")
    assert code == 0
    levels = {line.split(" | ")[1] for line in out.splitlines()}
    assert levels == {"L1"}
    code, out, _ = run("--chapter", "V6", "--level", "2")
    levels = {line.split(" | ")[1] for line in out.splitlines()}
    assert levels == {"L1", "L2"}


def test_exact_level():
    code, out, _ = run("--chapter", "V7", "--exact-level", "3")
    assert code == 0
    assert out.count("\n") == 1  # V7 has one L3 rule


def test_section_filter_and_standard_notation():
    code, out, _ = run("--section", "V6.2", "--level", "1")
    assert code == 0
    assert all(line.startswith("v5.0.0-6.2.") for line in out.splitlines())
    assert out.count("\n") == 8


def test_id_filter_with_cwe():
    code, out, _ = run("--id", "6.2.1", "v5.0.0-7.2.1", "--with-cwe")
    assert code == 0
    lines = out.splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("v5.0.0-6.2.1 | L1 |") and lines[0].endswith("| CWE-521")
    assert lines[1].startswith("v5.0.0-7.2.1 | L1 |")


def test_keyword_search_across_chapters():
    code, out, _ = run("--keyword", "jwt")
    assert code == 0
    assert all("jwt" in line.lower() for line in out.splitlines())
    ids = [line.split(" | ")[0] for line in out.splitlines()]
    assert any(i.startswith("v5.0.0-9.") for i in ids)
    assert any(not i.startswith("v5.0.0-9.") for i in ids)  # JWT is mentioned outside V9 too


def test_ids_format_groups_by_section_and_truncates():
    code, out, _ = run("--chapter", "V9", "--format", "ids")
    assert code == 0
    assert out.startswith("[V9.1]")
    assert all(len(line) <= 100 for line in out.splitlines())


def test_json_format_returns_full_rules():
    code, out, _ = run("--id", "1.2.5", "--format", "json")
    assert code == 0
    data = json.loads(out)
    assert len(data) == 1
    assert data[0]["id"] == "ASVS-V1-1.2.5"
    assert data[0]["cwe"]["id"] == 78
    assert data[0]["chapter"] == "V1"


def test_no_match_exits_nonzero_with_message():
    code, out, err = run("--keyword", "zzz-nothing-matches-this")
    assert code == 1
    assert out == ""
    assert "no requirements match" in err


def test_unknown_chapter_fails_clearly():
    code, _, err = run("--chapter", "V99")
    assert code != 0
    assert "no rules file" in err


def test_all_rules_count():
    code, out, _ = run("--format", "ids")
    assert code == 0
    assert sum(1 for line in out.splitlines() if line.startswith("  v5.0.0-")) == 345
