# What is ASVS?

The **Application Security Verification Standard (ASVS)** is a set of measurable security requirements for web applications and services. It helps teams design, build, and assess software security in a consistent way.

## ASVS Scope

ASVS focuses on four ideas:

- **Application**: security controls in the software product itself.
- **Security**: each requirement must reduce risk.
- **Verification**: each requirement must be testable as pass/fail.
- **Standard**: requirements define *what must be true*, not optional advice.

ASVS does not fully define SDLC, CI/CD, hosting, or operations, but those still matter for real security. Components like WAFs, proxies, and load balancers may count when controls depend on them (e.g., rate limiting, caching, traffic restrictions). External processes outside app control (like backup operations) are usually out of scope.

## Requirements and Documentation

ASVS requirements are mandatory (“must”), not recommendations (“should”). They target security outcomes without forcing one technology or implementation style.

Many controls depend on organization-specific decisions (e.g., allowed file types, input rules, session policy, data protection levels). ASVS therefore includes **documentation requirements** so those decisions are written down and can be verified against actual implementation.

Typical structure:

- First: document security decisions.
- Then: implement and verify those decisions in code/config.

This adds consistency, enables auditing, and supports flexibility for different business contexts.

## ASVS Levels

ASVS has three priority-based levels:

- **L1 (Level 1)**: minimum baseline, low barrier to entry, focuses on critical/common attack defenses (~20% of requirements).
- **L2 (Level 2)**: target for most applications; includes L1 + L2 requirements (~70% total implementation).
- **L3 (Level 3)**: highest assurance; adds advanced/depth controls (~final 30%).

Levels are based on risk reduction vs. implementation effort. Organizations may adopt higher-level controls earlier if risk justifies it.

## Choosing a Level

ASVS does not force one level for all apps. Teams should choose based on:

- business risk,
- data sensitivity,
- user/customer trust expectations,
- regulatory obligations.

Example: a low-risk startup may start at L1; a bank may need L3.

## ASVS Structure and Versioning

ASVS contains ~350 requirements across 17 chapters and multiple sections. This modular structure helps teams ignore irrelevant areas (e.g., OAuth chapter if OAuth is not used).

Versioning follows **Major.Minor.Patch**:

- **Major**: large rework; identifiers may change; full reassessment needed.
- **Minor**: requirements may be added/removed; reassessment still needed.
- **Patch**: non-breaking adjustments; prior compliance should still hold.

## Flexibility and Forking

Organizations are encouraged to create tailored ASVS forks for their domain/risk profile, while preserving traceability of requirement meaning. A common approach:

1. Start from L1 baseline.
2. Remove irrelevant sections.
3. Add stricter controls for higher-risk systems.
4. Progress toward L2/L3 where needed.

## Requirement Referencing

Requirement IDs use `<chapter>.<section>.<requirement>` (e.g., `1.2.5`).
Best practice is to include version: `v<version>-<id>` (e.g., `v5.0.0-1.2.5`) to avoid ambiguity when standards evolve.

Machine-readable exports (CSV/JSON) support tooling and automation.

## Practical Uses of ASVS

ASVS can be used as:

1. **Security architecture guidance**
   Helps architects choose robust controls and data protection patterns.
2. **Secure coding reference**
   Forms the basis for organization-specific developer guidance and approved security libraries.
3. **Unit/integration test guide**
   Enables security-focused automated tests and abuse-case testing (e.g., injection, brute force, enumeration, weak password handling).
4. **Training framework**
   Teaches what secure software should include, not only what attacks exist.
5. **Procurement baseline**
   Lets buyers require software or vendors to meet a specific ASVS level and provide evidence.

## Applying ASVS in Real Environments

Different sectors face different threats, assets, and compliance duties. Organizations should assess their own risk and choose the ASVS level and controls that match their operational reality.
