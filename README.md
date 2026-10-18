# appsec-review-skill

An [Agent Skill](https://agentskills.io) for checking applications against the
[OWASP Application Security Verification Standard (ASVS) 5.0.0](https://owasp.org/www-project-application-security-verification-standard/).

It includes the full ASVS 5.0.0 text and 345 requirements as machine-readable rules,
one file per chapter (V1–V17), each tagged with its level (L1–L3) and, where one is
known, a CWE. The agent chooses the relevant chapters for the code or question, checks
each requirement against evidence in your repository, and reports PASS / FAIL /
PARTIAL / N/A / UNVERIFIED with file references.

The skill uses the open `SKILL.md` format, so the same folder works in Claude Code,
GitHub Copilot, OpenCode and other agents that support Agent Skills.

## Install

The skill is the folder [`skills/appsec-review/`](skills/appsec-review/). To install it, copy that folder
into your agent's skills directory.

```sh
git clone https://github.com/bbaassssiiee/appsec-review-skill.git
```

| Agent | Project (commit it with your repo) | User (all projects) |
|---|---|---|
| Claude Code | `.claude/skills/appsec-review/` | `~/.claude/skills/appsec-review/` |
| GitHub Copilot | `.github/skills/appsec-review/` | `~/.copilot/skills/appsec-review/` |
| OpenCode | `.opencode/skills/appsec-review/` | `~/.config/opencode/skills/appsec-review/` |

For example, to install for your user account:

```sh
cp -r appsec-review-skill/skills/appsec-review ~/.claude/skills/appsec-review
```

Copilot and OpenCode also read `.claude/skills/`, so a single copy there works for
all three agents.

### Claude Code plugin

This repository is also a Claude Code plugin marketplace:

```text
/plugin marketplace add bbaassssiiee/appsec-review-skill
/plugin install appsec-review@appsec-review-skill
```

## Usage

Ask in plain language. The skill triggers on ASVS, OWASP, security requirements and
secure code review:

- "Check the login flow in `src/auth` against ASVS L2."
- "Which ASVS requirements apply to our file upload endpoint?"
- "Do an ASVS L1 review of this PR."
- "What does ASVS require for JWT validation?"

If you don't give a level, the skill checks at L2 and says so in the report.

The agent does not read whole chapters. It first inventories the code, triages the
ASVS sections against that inventory, and then pulls in only the applicable
requirements with the bundled query script:

```sh
skills/appsec-review/scripts/asvs-rules.py --chapter V6 --format sections   # what is in V6
skills/appsec-review/scripts/asvs-rules.py --section V6.2 V6.3 --level 2     # full text of two sections
skills/appsec-review/scripts/asvs-rules.py --keyword jwt --level 2           # across all chapters
skills/appsec-review/scripts/asvs-rules.py --id 6.2.1 --with-cwe             # one requirement
```

The script needs only Python 3 (PyYAML is used when present) and is handy on its own,
for example to look up a requirement from the terminal.

The report is rendered from a small findings file rather than typed out, so ids are
checked against the standard, the CWE links and levels are filled in from the rules,
and the summary counts are computed:

```sh
skills/appsec-review/scripts/asvs-report.py --example > findings.json   # the format
skills/appsec-review/scripts/asvs-report.py findings.json -o asvs-report.md
skills/appsec-review/scripts/asvs-report.py findings.json --format json # for CI or tooling
```

A `PASS` is one table row with its evidence. Every `FAIL` and `PARTIAL` gets a Findings
entry: the requirement, what was found, why it matters (the mapped CWE weakness and its
typical consequence, plus what it means for this application) and the fix. The CWE
mapping is there to teach, not just to tag. For a design document there is no
code to cite; the agent then works from `assets/design-review-checklist.md`, which maps
the documentation and design requirements to questions.

## Layout

```text
skills/appsec-review/   the skill (this is what gets installed)
  SKILL.md              instructions: routing, triage, procedure, report format
  scripts/asvs-rules.py query the rules by chapter, section, level, id or keyword
  scripts/asvs-report.py render and validate the report from a findings file
  assets/               findings-file schema and the design-review checklist
  rules/                asvs-v<N>-rules.yml, one per chapter
  references/           ASVS 5.0.0 chapters and appendices (Markdown)
tests/                  pytest suite for the skill scripts
scripts/                maintainer tooling, not part of the installed skill
  generate-asvs-rules.sh  rebuild rules/ from references/ (runs the CWE enrichment)
  enrich-rules-with-cwe.py  add CWE fields to the rules
  asvs-5.0.0-cwe-mapping.yml  ASVS id → CWE id mapping
  asvs.sh               consistency check (rules vs. references)
  check-skill.py        SKILL.md format check (name, description, referenced files)
.claude-plugin/         Claude Code plugin and marketplace manifests
.github/workflows/      CI: runs pre-commit on every push and pull request
```

## Maintaining

Validation runs through [pre-commit](https://pre-commit.com), both locally and in
GitHub Actions (`.github/workflows/validate.yml`):

```sh
pre-commit install                  # run the checks on every commit
pre-commit run --all-files          # SKILL.md format, rules vs. references, YAML/JSON, whitespace
```

Individual checks and the rules generator:

```sh
scripts/check-skill.py              # SKILL.md frontmatter and referenced files
scripts/asvs.sh verify              # every requirement in references/ has a rule
python3 -m pytest -q tests          # the skill scripts, with and without PyYAML
scripts/asvs.sh stats               # rule counts per chapter

# Rebuilding the rules needs the CWE-699 XML view from
# https://cwe.mitre.org/data/downloads.html saved as scripts/cwe.xml (or set CWE_XML).
scripts/generate-asvs-rules.sh
CWE_CATALOG=/path/to/cwec_v4.20.xml scripts/generate-asvs-rules.sh   # also resolve CWEs outside the view
```

## Testing the skill itself

`evals/` holds two kinds of test material:

- `trigger-evals.json`: prompts that should and should not make an agent pick this
  skill. The negatives are near-misses (CWE lookups, OS hardening, SOC 2, a PR review
  with no security angle), not unrelated tasks.
- `evals.json`: task prompts with assertions on the result (guard emoji, only the
  applicable sections loaded, Sections N/A line, remediation per failure, findings file
  that validates). Evals 3 and 4 need a repository with a login flow to run against.

Measuring triggering needs the `claude` CLI and Anthropic's
[skill-creator](https://github.com/anthropics/skills) skill, which has the loop:

```sh
# one-off check of a single prompt
claude -p "Is ons wachtwoordbeleid streng genoeg? Minimaal 6 tekens, geen MFA." --verbose | grep -i appsec-review

# the full loop: scores the current description, proposes a better one, re-scores
cd <skill-creator>
python -m scripts.run_loop --eval-set <repo>/evals/trigger-evals.json \
  --skill-path <repo>/skills/appsec-review --max-iterations 5 --verbose
```

Paste the resulting `best_description` into `SKILL.md` and run `pytest` so the
trigger words stay covered.

## License

[CC BY-SA 4.0](LICENSE). The ASVS content is © 2008-2025 The OWASP Foundation and
is licensed under CC BY-SA 4.0. The CWE mappings are indicative only; they come from
the ASVS 5.0 "bleeding edge" draft, and ASVS 5.0.0 itself does not include CWE
mappings.
