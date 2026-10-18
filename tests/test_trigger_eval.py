"""The vendored trigger-eval loop stays importable and its CLI parses."""
import os
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.parametrize("module", ["run_loop", "run_eval", "improve_description", "generate_report"])
def test_module_help(module):
    proc = subprocess.run([sys.executable, "-m", f"scripts.trigger_eval.{module}", "--help"],
                          cwd=REPO, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "usage:" in proc.stdout


def test_parse_skill_md_reads_our_skill():
    sys.path.insert(0, REPO)
    from pathlib import Path
    from scripts.trigger_eval.utils import parse_skill_md
    name, description, _ = parse_skill_md(Path(REPO) / "skills" / "appsec-review")
    assert name == "appsec-review"
    assert "ASVS" in description


def test_license_is_vendored():
    assert os.path.exists(os.path.join(REPO, "scripts", "trigger_eval", "LICENSE.txt"))
