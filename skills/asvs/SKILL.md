---
name: asvs
description: Verify code, designs, and configuration against the OWASP Application Security Verification Standard (ASVS) 5.0.0 at Level 1, 2, or 3. Use when the user mentions ASVS, OWASP, verification requirements, application security requirements, a secure code review, security hardening, or asks which security requirements apply to a feature, component, or SDLC phase (plan, code, test, build, deploy, operate). Routes to the relevant ASVS chapters (V1-V17), checks each requirement against evidence, and reports gaps with CWE references.
license: CC-BY-SA-4.0
---

# OWASP ASVS 5.0.0

This skill holds the full text of OWASP ASVS 5.0.0 (`references/`) and one machine-readable rules file per chapter (`rules/`). Use it to check whether an application meets the ASVS requirements, and to back each verdict with evidence.

## Output style

Start every message produced under this skill with `💂🏼`, including questions, menus, summaries, and conclusions. Code blocks are not prefixed.

## Files

| Path | Content |
|---|---|
| `rules/asvs-v<N>-rules.yml` | Requirements for chapter V<N>, one entry per requirement. Read these first. |
| `references/0x1?-V<N>-*.md`, `references/0x2?-V<N>-*.md` | The ASVS chapter text: control objectives, section introductions, and the original requirement tables. Read when you need context or rationale. |
| `references/0x03-What-is-the-ASVS.md` | Scope and the meaning of the levels |
| `references/0x92-Appendix-C_Cryptography.md` | Approved algorithms, key sizes, and modes (needed for V11) |
| `references/0x90-Appendix-A_Glossary.md` | Terms used in the requirements |
| `references/README.md` | Index of all reference files |

Structure of a rules file:

```yaml
meta:
  chapter: "V6"
  title: "Authentication"
  requirements: 47
  per_level: {L1: 13, L2: 22, L3: 12}
  sections: [{id: "V6.1", title: "..."}]
rules:
  - id: "ASVS-V6-6.2.1"    # ASVS-V<chapter>-<ASVS requirement id>
    section: "V6.2"
    level: 1                # 1, 2 or 3
    rule: "User set passwords are at least 8 characters in length ..."
    cwe:                    # optional, indicative only
      id: 521
      name: "Weak Password Requirements"
      url: "https://cwe.mitre.org/data/definitions/521.html"
```

When citing a requirement, use the ASVS notation `v5.0.0-<id>`, for example `v5.0.0-6.2.1`.

## Chapters

| Chapter | Title | Rules | L1 / L2 / L3 | Reference |
|---|---|---|---|---|
| V1 | Encoding and Sanitization | `rules/asvs-v1-rules.yml` | 8 / 19 / 3 | `references/0x10-V1-Encoding-and-Sanitization.md` |
| V2 | Validation and Business Logic | `rules/asvs-v2-rules.yml` | 4 / 7 / 2 | `references/0x11-V2-Validation-and-Business-Logic.md` |
| V3 | Web Frontend Security | `rules/asvs-v3-rules.yml` | 8 / 11 / 12 | `references/0x12-V3-Web-Frontend-Security.md` |
| V4 | API and Web Service | `rules/asvs-v4-rules.yml` | 2 / 8 / 6 | `references/0x13-V4-API-and-Web-Service.md` |
| V5 | File Handling | `rules/asvs-v5-rules.yml` | 4 / 5 / 4 | `references/0x14-V5-File-Handling.md` |
| V6 | Authentication | `rules/asvs-v6-rules.yml` | 13 / 22 / 12 | `references/0x15-V6-Authentication.md` |
| V7 | Session Management | `rules/asvs-v7-rules.yml` | 6 / 12 / 1 | `references/0x16-V7-Session-Management.md` |
| V8 | Authorization | `rules/asvs-v8-rules.yml` | 4 / 3 / 6 | `references/0x17-V8-Authorization.md` |
| V9 | Self-contained Tokens | `rules/asvs-v9-rules.yml` | 4 / 3 / 0 | `references/0x18-V9-Self-contained-Tokens.md` |
| V10 | OAuth and OIDC | `rules/asvs-v10-rules.yml` | 5 / 24 / 7 | `references/0x19-V10-OAuth-and-OIDC.md` |
| V11 | Cryptography | `rules/asvs-v11-rules.yml` | 3 / 11 / 10 | `references/0x20-V11-Cryptography.md` |
| V12 | Secure Communication | `rules/asvs-v12-rules.yml` | 3 / 6 / 3 | `references/0x21-V12-Secure-Communication.md` |
| V13 | Configuration | `rules/asvs-v13-rules.yml` | 1 / 12 / 8 | `references/0x22-V13-Configuration.md` |
| V14 | Data Protection | `rules/asvs-v14-rules.yml` | 2 / 7 / 4 | `references/0x23-V14-Data-Protection.md` |
| V15 | Secure Coding and Architecture | `rules/asvs-v15-rules.yml` | 3 / 10 / 8 | `references/0x24-V15-Secure-Coding-and-Architecture.md` |
| V16 | Security Logging and Error Handling | `rules/asvs-v16-rules.yml` | 0 / 16 / 1 | `references/0x25-V16-Security-Logging-and-Error-Handling.md` |
| V17 | WebRTC | `rules/asvs-v17-rules.yml` | 0 / 7 / 5 | `references/0x26-V17-WebRTC.md` |

## Levels

- **L1**: the minimum for any application. Start here.
- **L2**: for applications handling sensitive data or transactions. This is the right target for most applications.
- **L3**: for the most critical applications (high value, safety, or regulatory impact).

Checking at level N means checking every rule with `level <= N`. Use the level the user asks for. If they don't specify one, use **L2** and say so in the report.

## Routing

Load only the chapters that apply. Choose them by what is being verified. If only an SDLC phase is given, route by phase.

### By topic

| The code or question involves | Chapters |
|---|---|
| Output to HTML, SQL, shell, LDAP, XML, templates; parsing; deserialization; memory-unsafe code | V1 |
| Input validation, business rules, workflow, rate limiting, anti-automation | V2 |
| Browser-facing responses, cookies, security headers, CSP, CORS, redirects | V3 |
| REST, GraphQL, WebSocket, HTTP message handling | V4 |
| File upload, download, storage, archives, paths | V5 |
| Login, passwords, MFA, credential recovery, identity providers | V6 |
| Sessions, logout, session timeouts, re-authentication | V7 |
| Permissions, roles, object-level and function-level access control, multi-tenancy | V8 |
| JWT, SAML assertions, other signed or encrypted tokens | V9 |
| OAuth 2 clients, authorization servers, resource servers, OpenID Connect | V10 |
| Encryption, hashing, randomness, keys, certificates, secrets in code | V11 (and Appendix C) |
| TLS, HTTPS, service-to-service communication | V12 |
| Configuration, secrets management, deployment settings, debug features, unintended exposure | V13 |
| Personal or sensitive data, data classification, caching, client-side storage | V14 |
| Architecture, dependencies and SBOM, dangerous functionality, concurrency, safe coding patterns | V15 |
| Logging, audit trails, error handling, exception messages | V16 |
| WebRTC, TURN/STUN, media servers, signaling | V17 |

### By SDLC phase

| Phase | Chapters |
|---|---|
| Plan and design | V2, V8, V11, V14, V15 |
| Code and code review | V1, V2, V3, V4, V5, V6, V7, V8, V9, V10, V11, V15, V16, V17 (drop the ones that aren't relevant to the technology) |
| Test | V1, V2, V3, V4, V5, V6, V7, V8, V9, V10 |
| Build and dependencies | V13, V15 |
| Deploy and configuration | V3, V12, V13 |
| Operate and monitor | V13, V16 |

When the user names more than one phase, combine the chapters, remove duplicates, and keep them in chapter order. Skip chapters that clearly don't apply to the system. For example, skip V17 when there is no WebRTC and V10 when there is no OAuth. List the skipped chapters in the report.

## Procedure

1. **Scope**: decide what is being verified (repository, directory, diff or PR, design document, or configuration), which technologies it uses, and the target level.
2. **Route**: pick the chapters using the tables above.
3. **Load the rules**: read `rules/asvs-v<N>-rules.yml` for each chapter and keep the rules with `level <= target`. Open the reference chapter only for requirements whose intent is unclear.
4. **Collect evidence**: for each rule, search the code, configuration, tests, pipeline definitions, and docs. Cite concrete locations (`path:line`), test names, or config keys.
5. **Judge** each rule:
   - `PASS`: evidence shows the requirement is met.
   - `FAIL`: evidence shows it is not met. Say what is wrong and where.
   - `PARTIAL`: met in some places but not all.
   - `N/A`: the feature doesn't exist in scope. Give the reason.
   - `UNVERIFIED`: can't be decided from the available material. Say what evidence is missing.
6. **Report** as below.

Don't mark a rule `PASS` without evidence. Leaving a rule `UNVERIFIED` is better than guessing.

## Report format

```markdown
💂🏼 ASVS 5.0.0 verification: <scope>, target L<n>
Chapters: V6, V7, V8 (skipped: V17 no WebRTC)

| Requirement | L | Status | Evidence / finding | CWE |
|---|---|---|---|---|
| v5.0.0-6.2.1 | 1 | FAIL | `auth/password.py:42` minimum length is 6 | [CWE-521](https://cwe.mitre.org/data/definitions/521.html) |
| v5.0.0-7.2.1 | 1 | PASS | `session.ts:18` tokens validated server side | |

Summary: <n> PASS, <n> FAIL, <n> PARTIAL, <n> N/A, <n> UNVERIFIED

Top risks
1. ...

Missing evidence
- ...
```

In the CWE column, write each CWE as a Markdown link to its MITRE page: `CWE-<ID>` links to `https://cwe.mitre.org/data/definitions/<ID>.html`, where `<ID>` is the number only (so `CWE-78` becomes `[CWE-78](https://cwe.mitre.org/data/definitions/78.html)`). Separate multiple CWEs with a comma, and leave the cell empty when there is no mapping.

For a quick question such as "which requirements apply to X?", skip the table and list the relevant requirement IDs with one-line summaries.

## Attribution

The content in `references/` and `rules/` is derived from the OWASP Application Security Verification Standard 5.0.0, © 2008-2025 The OWASP Foundation, licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). The CWE mappings come from the ASVS 5.0 draft ("bleeding edge") mapping and are indicative only.
