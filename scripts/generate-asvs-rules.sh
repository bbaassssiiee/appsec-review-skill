#!/usr/bin/env bash
# Distill references/0x1*-V*.md / 0x2*-V*.md (OWASP ASVS 5.0.0) into rules/asvs-v<N>-rules.yml.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="${SKILL_DIR:-$(dirname "$SCRIPT_DIR")/skills/appsec-review}"
REF_DIR="${SKILL_DIR}/references"
OUT_DIR="${SKILL_DIR}/rules"

CWE_XML="${CWE_XML:-${SCRIPT_DIR}/cwe.xml}"
[[ -f "$CWE_XML" ]] || { echo "error: $CWE_XML not found; download the CWE-699 view (XML) from https://cwe.mitre.org/data/downloads.html or set CWE_XML" >&2; exit 1; }
export CWE_XML SKILL_DIR

mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/asvs-v*-rules.yml

for src in "$REF_DIR"/0x[12][0-9]-V*.md; do
  base="$(basename "$src")"
  chapter="$(sed -nE 's/^# V([0-9]+) .*/\1/p' "$src" | head -1)"
  out="${OUT_DIR}/asvs-v${chapter}-rules.yml"

  awk -v src="references/${base}" -v out_name="asvs-v${chapter}-rules.yml" '
  function trim(s){gsub(/^[ \t]+|[ \t]+$/, "", s); return s}
  function yq(s){gsub(/\\/, "\\\\", s); gsub(/"/, "\\\"", s); return "\"" s "\""}
  /^# V[0-9]+ / {
    chapter = $2; sub(/^V/, "", chapter)
    title = $0; sub(/^# V[0-9]+ /, "", title)
    next
  }
  /^## V[0-9]+\.[0-9]+ / {
    section = $2; sub(/^V/, "", section)
    stitle = $0; sub(/^## V[0-9]+\.[0-9]+ /, "", stitle)
    nsec++; sec_id[nsec] = section; sec_title[nsec] = stitle
    next
  }
  /^\| \*\*[0-9]+\.[0-9]+\.[0-9]+\*\* \|/ {
    split($0, cols, "|")
    id = trim(cols[2]); gsub(/\*/, "", id)
    text = trim(cols[3])
    level = trim(cols[4]) + 0
    sub(/^Verify that /, "", text)
    text = toupper(substr(text, 1, 1)) substr(text, 2)
    n++
    r_id[n] = id; r_sec[n] = section; r_level[n] = level; r_text[n] = text
    lvl[level]++
  }
  END {
    printf "# %s\n", out_name
    printf "# Verifiable requirements distilled from OWASP ASVS 5.0.0 - V%s %s.\n", chapter, title
    print  "meta:"
    print  "  prefix: \"ASVS\""
    print  "  standard: \"OWASP ASVS 5.0.0\""
    printf "  source: %s\n", yq(src)
    printf "  chapter: \"V%s\"\n", chapter
    printf "  title: %s\n", yq(title)
    printf "  requirements: %d\n", n
    printf "  per_level: {L1: %d, L2: %d, L3: %d}\n", lvl[1], lvl[2], lvl[3]
    print  "  sections:"
    for (i = 1; i <= nsec; i++) {
      printf "    - id: \"V%s\"\n", sec_id[i]
      printf "      title: %s\n", yq(sec_title[i])
    }
    print "rules:"
    for (i = 1; i <= n; i++) {
      printf "  - id: %s\n", yq("ASVS-V" chapter "-" r_id[i])
      printf "    section: \"V%s\"\n", r_sec[i]
      printf "    level: %d\n", r_level[i]
      printf "    rule: %s\n", yq(r_text[i])
    }
  }
  ' "$src" > "$out"

  echo "Generated rules/$(basename "$out") ($(grep -c '^  - id: "ASVS-' "$out") rules)"
done

# Add CWE fields (id, name, url, consequence note) from scripts/cwe.xml (or $CWE_XML).
# Set CWE_CATALOG=/path/to/cwec_vX.Y.xml to also resolve CWEs outside the CWE-699 view.
python3 "${SCRIPT_DIR}/enrich-rules-with-cwe.py" --quiet ${CWE_CATALOG:+--catalog "$CWE_CATALOG"}
