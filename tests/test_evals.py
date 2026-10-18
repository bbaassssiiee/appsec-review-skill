"""Keep the eval files well-formed so the skill-creator tooling can read them."""
import json
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVALS = os.path.join(REPO, "evals")
SKILL_MD = os.path.join(REPO, "skills", "appsec-review", "SKILL.md")


def load(name):
    with open(os.path.join(EVALS, name), encoding="utf-8") as fh:
        return json.load(fh)


def test_trigger_evals_shape_and_balance():
    items = load("trigger-evals.json")
    assert isinstance(items, list) and len(items) >= 16
    for it in items:
        assert set(it) == {"query", "should_trigger"}, it
        assert isinstance(it["query"], str) and len(it["query"]) > 20
        assert isinstance(it["should_trigger"], bool)
    positives = sum(1 for it in items if it["should_trigger"])
    negatives = len(items) - positives
    assert positives >= 8 and negatives >= 8
    assert len({it["query"] for it in items}) == len(items)


def test_trigger_positives_cover_the_trigger_words():
    items = [it["query"].lower() for it in load("trigger-evals.json") if it["should_trigger"]]
    for word in ("asvs", "owasp", "appsec", "application security"):
        assert any(word in q for q in items), f"no positive query mentions {word!r}"
    # and at least two positives rely on none of them (implicit triggering)
    implicit = [q for q in items if not any(w in q for w in ("asvs", "owasp", "appsec", "application security"))]
    assert len(implicit) >= 2


def test_trigger_negatives_avoid_the_trigger_words():
    items = [it["query"].lower() for it in load("trigger-evals.json") if not it["should_trigger"]]
    for q in items:
        for word in ("asvs", "owasp", "appsec", "application security"):
            assert word not in q, f"negative query contains the trigger word {word!r}: {q}"


def test_functional_evals_shape():
    doc = load("evals.json")
    assert doc["skill_name"] == "appsec-review"
    ids = [e["id"] for e in doc["evals"]]
    assert ids == sorted(ids) and len(set(ids)) == len(ids)
    for e in doc["evals"]:
        assert {"id", "name", "prompt", "expected_output", "files", "assertions"} <= set(e)
        assert re.fullmatch(r"[a-z0-9-]+", e["name"])
        assert len(e["assertions"]) >= 4
        for a in e["assertions"]:
            assert set(a) == {"text", "check"} and a["text"] and a["check"]
        assert any("💂🏼" in a["check"] for a in e["assertions"])


def test_description_names_the_trigger_words():
    with open(SKILL_MD, encoding="utf-8") as fh:
        head = fh.read().split("---", 2)[1]
    desc = re.search(r"^description:\s*(.+)$", head, re.M).group(1).lower()
    for word in ("asvs", "owasp", "appsec", "application security"):
        assert word in desc, f"description does not mention {word!r}"
    assert len(desc) <= 1024
