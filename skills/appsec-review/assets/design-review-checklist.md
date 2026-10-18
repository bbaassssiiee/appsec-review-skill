# ASVS design review checklist

Use this in the plan and design phase, when there is no code to cite. Each question
maps to the ASVS 5.0.0 requirements in brackets; the answer is the evidence. Ask only
the groups that the inventory makes relevant, and record the answers as findings
(`PASS` when the design document answers it, `UNVERIFIED` when nobody can, `N/A` with
a reason when the feature is absent).

Questions marked L2 or L3 apply only at that level or above; unmarked questions are L1.

## Data and business rules (V2, V14)

- Which input validation rules apply to each data item, and where are they written down? [2.1.1]
- How is consistency between combined data items checked (for example suburb and postal code)? (L2) [2.1.2]
- What per-user and global business-logic limits exist (quantities, amounts, frequencies)? (L2) [2.1.3]
- Which data is sensitive, and into which protection levels is it classified? Include data that is only encoded, such as JWT payloads. (L2) [14.1.1]
- For each protection level: what are the requirements for encryption, integrity, retention, logging and access control? (L2) [14.1.2]

## Authentication (V6)

- How do rate limiting, anti-automation and adaptive response defend against credential stuffing and brute force, and how is malicious account lockout prevented? [6.1.1]
- Which context-specific words (organization, product, project names) are blocked in passwords? (L2) [6.1.2]
- If there is more than one authentication pathway, are they documented together with the controls and strength enforced on each? (L2) [6.1.3]

## Sessions (V7)

- What are the inactivity timeout and absolute session lifetime, and how are deviations from NIST SP 800-63B justified? (L2) [7.1.1]
- How many concurrent sessions may one account have, and what happens when the limit is reached? (L2) [7.1.2]
- In a federated (SSO) setup, which systems manage sessions and how are lifetimes, termination and re-authentication coordinated? (L2) [7.1.3]

## Authorization (V8)

- What rules restrict function-level and data-specific access based on consumer permissions and resource attributes? [8.1.1]
- What rules restrict field-level read and write access, including rules that depend on the object's state? (L2) [8.1.2]
- Which environmental and contextual attributes (time, location, IP, device) feed security decisions? (L3) [8.1.3]
- How are those attributes evaluated: thresholds, risk levels and the resulting action (allow, challenge, deny)? (L3) [8.1.4]

## Files (V5)

- For each upload feature: permitted types, expected extensions, maximum size including unpacked size, and how files are made safe to download and process? (L2) [5.1.1]

## Web frontend (V3)

- Which browser security features must be supported (HTTPS, HSTS, CSP, ...), and how does the application behave when they are missing? (L3) [3.1.1]

## Cryptography (V11)

- Is there a key management policy and key lifecycle following a standard such as NIST SP 800-57, including limits on key sharing? (L2) [11.1.1]
- Is there a cryptographic inventory of keys, algorithms and certificates, stating where each key may be used and which data it may protect? (L2) [11.1.2]
- Are discovery mechanisms in place to find all uses of cryptography in the system? (L3) [11.1.3]
- Does the inventory include a migration plan to new standards such as post-quantum cryptography? (L3) [11.1.4]

## Communication and configuration (V12, V13)

- Which external services does the application connect to, and can an end user supply a destination? (L2) [13.1.1]
- Per service: connection limits and behaviour when they are reached? (L3) [13.1.2]
- Per external resource: release procedures, timeouts, failure handling and where retries live? (L3) [13.1.3]
- Which secrets are critical, and on what schedule are they rotated? (L3) [13.1.4]

## Architecture and dependencies (V15)

- What are the remediation time frames for vulnerable third-party components and for updates in general? [15.1.1]
- Is there an inventory (SBOM) of third-party libraries, with sources restricted to trusted, maintained repositories? (L2) [15.1.2]
- Which functionality is time-consuming or resource-demanding, and how is loss of availability prevented? (L2) [15.1.3]
- Which third-party libraries are considered risky components? (L3) [15.1.4]
- Where is dangerous functionality used, and what extra protection surrounds it? (L3) [15.1.5]

## Logging (V16)

- Is there an inventory of logging per layer: events, formats, storage, use, access control and retention? (L2) [16.1.1]

## Derived from the OWASP Application Security Verification Standard 5.0.0

© 2008-2025 The OWASP Foundation, CC BY-SA 4.0. Question wording is the skill's; the
requirement ids are the authority. Run `scripts/asvs-rules.py --id <id>` for the full text.
