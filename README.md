# appsec-review

A Claude Code plugin that reviews code, pull requests, designs and configuration
against the
[OWASP Application Security Verification Standard (ASVS) 5.0.0](https://owasp.org/www-project-application-security-verification-standard/).

It bundles the full ASVS 5.0.0 text and all 345 requirements as machine-readable
rules, one file per chapter (V1–V17). Each rule is tagged with its level (L1–L3)
and, where one is known, a CWE. The agent picks the chapters that fit your code or
question, checks each requirement against evidence in your repository, and reports
`PASS` / `FAIL` / `PARTIAL` / `N/A` / `UNVERIFIED` with file references, the risk
behind every failure, and a concrete fix.

The plugin contains no executable code: only Markdown, YAML and a JSON schema. It
makes no network requests. The agent gathers evidence with its own normal tools
(reading files, searching the repository).

## Install

### Claude Code plugin

The plugin is published through the
[`bas-ai-skills`](https://github.com/bbaassssiiee/bas-ai-skills) marketplace:

```text
/plugin marketplace add bbaassssiiee/bas-ai-skills
/plugin install appsec-review@bas-ai-skills
```

To try it from a local clone without installing:

```text
git clone https://github.com/bbaassssiiee/appsec-review-skill.git
claude --plugin-dir ./appsec-review-skill
```

### As a plain Agent Skill

The skill uses the open [`SKILL.md`](https://agentskills.io) format, so the folder
[`skills/appsec-review/`](skills/appsec-review/) also works without the plugin
wrapper, in Claude Code, GitHub Copilot, OpenCode and other agents that support
Agent Skills. Copy it into the agent's skills directory:

| Agent | Project (commit it with your repo) | User (all projects) |
|---|---|---|
| Claude Code | `.claude/skills/appsec-review/` | `~/.claude/skills/appsec-review/` |
| GitHub Copilot | `.github/skills/appsec-review/` | `~/.copilot/skills/appsec-review/` |
| OpenCode | `.opencode/skills/appsec-review/` | `~/.config/opencode/skills/appsec-review/` |

```text
cp -r appsec-review-skill/skills/appsec-review ~/.claude/skills/appsec-review
```

Copilot and OpenCode also read `.claude/skills/`, so a single copy there serves all
three agents.

## Usage

Ask in plain language. The skill triggers on ASVS, OWASP, CWE, application security
requirements and secure code review:

- "Check the login flow in `src/auth` against ASVS L2."
- "Do an ASVS L1 review of this PR."
- "Which ASVS requirements apply to our file upload endpoint?"
- "What does ASVS require for JWT validation?"
- "Review this design for application security requirements before we build it."

You can also invoke it explicitly:

```text
/appsec-review:appsec-review check src/auth at L2
```

(As a plain skill, without the plugin, the command is `/appsec-review`.)

### Choosing a level

| Level | Use for |
|---|---|
| L1 | The minimum for any application |
| L2 | Applications handling sensitive data or transactions; the right target for most |
| L3 | The most critical applications: high value, safety, or regulatory impact |

Checking at level N covers every requirement at that level and below. If you don't
name a level, the skill checks at **L2** and says so in the report.

### What you can review

| Scope | What happens |
|---|---|
| Repository or directory | Full review of the security-relevant features found there |
| Diff or pull request | Only the requirements the change can affect; the rest is out of scope |
| Design document or proposal | A question-driven review from the design checklist; unanswered questions are reported so the author knows what to add |
| Configuration and deployment | The configuration, communication and secrets chapters |
| A quick question | A short list of the relevant requirement ids, no report |

You can also scope by SDLC phase ("what applies at build time?") or by topic
("sessions", "OAuth", "logging").

### How a review runs

1. **Scope** — what is being verified, and the target level.
2. **Inventory** — the security-relevant features in scope: entry points,
   authentication mechanisms, token formats, file handling, crypto, external services.
3. **Route** — pick the ASVS chapters that match the inventory.
4. **Triage** — drop whole sections for features that don't exist (no WebRTC, no
   OAuth, no file upload), with the reason.
5. **Collect evidence and judge** — each remaining requirement gets a verdict backed
   by a `path:line`, test name or config key. No `PASS` without evidence.
6. **Report** — see below.

A whole application at L2 means 100 to 150 requirements and a long report. The agent
says so up front and works L1 first; ask for one feature, one chapter, a pull request
or L1 only when that is what you need.

### The report

```markdown
ASVS 5.0.0 verification: src/auth, target L2
Inventory: web UI + REST API, password login with TOTP, opaque server-side sessions
Chapters: V6, V7, V8 (skipped: V17 no WebRTC)
Sections N/A: V6.6 (no out-of-band auth), V6.7 (no cryptographic authenticators)
Sections UNVERIFIED: V6.1, V7.1, V8.1 (design documentation not in scope)

| Requirement | L | Status | Evidence / finding | CWE |
|---|---|---|---|---|
| v5.0.0-6.2.1 | 1 | FAIL | `auth/password.py:42` minimum length is 6 | [CWE-521](https://cwe.mitre.org/data/definitions/521.html) |
| v5.0.0-7.2.1 | 1 | PASS | `session.ts:18` tokens validated server side | |

Summary: 1 PASS, 1 FAIL, 0 PARTIAL, 0 N/A, 0 UNVERIFIED

Findings

### v5.0.0-6.2.1 FAIL (L1)
Requirement: User set passwords are at least 8 characters in length ...
Found: `auth/password.py:42` minimum length is 6
Why it matters: CWE-521 Weak Password Requirements: ...
Fix: raise the minimum in `auth/password.py:42` to 8 (15 recommended) ...
```

| Status | Meaning |
|---|---|
| `PASS` | Evidence shows the requirement is met |
| `FAIL` | Evidence shows it is not met |
| `PARTIAL` | Met in some places but not all |
| `N/A` | The feature doesn't exist in scope |
| `UNVERIFIED` | Can't be decided from the available material; the report says what is missing |

A `PASS` is one table row. Every `FAIL` and `PARTIAL` gets a Findings entry with the
requirement, what was found, why it matters for this application and how to fix it,
ordered so L1 failures come first. The CWE mapping is there to teach, not just to tag.

## What's covered

| Chapter | Title | L1 / L2 / L3 |
|---|---|---|
| V1 | Encoding and Sanitization | 8 / 19 / 3 |
| V2 | Validation and Business Logic | 4 / 7 / 2 |
| V3 | Web Frontend Security | 8 / 11 / 12 |
| V4 | API and Web Service | 2 / 8 / 6 |
| V5 | File Handling | 4 / 5 / 4 |
| V6 | Authentication | 13 / 22 / 12 |
| V7 | Session Management | 6 / 12 / 1 |
| V8 | Authorization | 4 / 3 / 6 |
| V9 | Self-contained Tokens | 4 / 3 / 0 |
| V10 | OAuth and OIDC | 5 / 24 / 7 |
| V11 | Cryptography | 3 / 11 / 10 |
| V12 | Secure Communication | 3 / 6 / 3 |
| V13 | Configuration | 1 / 12 / 8 |
| V14 | Data Protection | 2 / 7 / 4 |
| V15 | Secure Coding and Architecture | 3 / 10 / 8 |
| V16 | Security Logging and Error Handling | 0 / 16 / 1 |
| V17 | WebRTC | 0 / 7 / 5 |

## Layout

```text
.claude-plugin/         plugin manifest (plugin.json) and icon
skills/appsec-review/   the skill
  SKILL.md              instructions: routing, triage, procedure, report format
  rules/                asvs-v<N>-rules.yml, one per chapter
  references/           ASVS 5.0.0 chapters and appendices (Markdown)
  assets/               design-review checklist and findings-file schema
evals/                  trigger and task evals for the skill
opencode.json           registers ./skills for OpenCode
```

## Versioning

The skill's version follows the ASVS release it implements:

| Part | Meaning | Example |
|---|---|---|
| `major.minor` | The ASVS version whose requirements are in `rules/` and `references/` | `5.0` = ASVS 5.0.0 |
| `patch` | Revision of the skill itself: instructions, routing, checklist, report format | `5.0.1` |

So `5.0.1` means "ASVS 5.0.0, second revision of the skill". A new ASVS release becomes a
new `major.minor` and resets the patch to `0`; ASVS point releases that only change
wording (5.0.0 → 5.0.1 upstream) still bump the skill's patch, with the exact upstream
version named in `meta.standard` of each rules file and in the `Attribution` section of
`SKILL.md`. Skill changes never bump `major.minor`, however large; the ASVS version is
what the user needs to know when reading a report that cites `v5.0.0-6.2.1`.

The version is kept in two places and they must agree: `.claude-plugin/plugin.json`
(`version`) and `skills/appsec-review/SKILL.md` (`version` in the frontmatter). CI
checks that they match.

## Contributing

Validation runs through [pre-commit](https://pre-commit.com), locally and in GitHub
Actions (`.github/workflows/validate.yml`):

```text
pre-commit install            # run the checks on every commit
pre-commit run --all-files    # YAML/JSON syntax, whitespace, large files
```

The workflow also runs a consistency job: every requirement in `references/` has
exactly one entry in `rules/`, every entry keeps the layout the search patterns in
`SKILL.md` rely on, and the chapter table in `SKILL.md` matches the rules files. The
check is inline in the workflow because the skill itself ships no scripts.

`evals/trigger-evals.json` holds prompts that should and should not trigger the
skill; `evals/evals.json` holds task prompts with assertions on the result. Eval 3
has a `fixture`: a public repository pinned to a commit, with assertions that name
findings a correct review must report (true positives) and rules it must pass (true
negatives), so the eval measures whether the review is right and not only whether the
report is well-formed. Clone the fixture at that commit and run the prompt from its
root. Run them
with the `run_eval.py`/`run_loop.py` scripts from Anthropic's
[skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
skill, pointing `--skill-path` at `skills/appsec-review`.

## License and attribution

Licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/); see
[LICENSE](LICENSE).

The content in `skills/appsec-review/references/` and `skills/appsec-review/rules/`
is derived from the OWASP Application Security Verification Standard 5.0.0,
© 2008–2025 The OWASP Foundation, licensed under CC BY-SA 4.0. The CWE mappings come
from the ASVS 5.0 draft mapping and are indicative only.

This is a review aid, not a certification: a clean report means no gaps were found in
the evidence examined, not that the application is ASVS-compliant.
