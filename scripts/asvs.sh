#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="${SKILL_DIR:-$(dirname "$SCRIPT_DIR")/skills/asvs}"
RULES_DIR="${SKILL_DIR}/rules"
REF_DIR="${SKILL_DIR}/references"
CHAPTERS=17

rules_file() {
  echo "${RULES_DIR}/asvs-v${1}-rules.yml"
}

ref_file() {
  ls "$REF_DIR"/0x[12][0-9]-V"${1}"-*.md 2>/dev/null | head -1
}

count_rules() {
  local file
  file="$(rules_file "$1")"
  [[ -f "$file" ]] || { echo 0; return; }
  grep -c '^  - id: "ASVS-' "$file" || true
}

count_refs() {
  local file
  file="$(ref_file "$1")"
  [[ -n "$file" ]] || { echo 0; return; }
  grep -cE '^\| \*\*[0-9]+\.[0-9]+\.[0-9]+\*\* \|' "$file" || true
}

print_usage() {
  cat <<'EOF'
Usage:
  asvs.sh verify   # check that every reference requirement has a rule (per chapter + total)
  asvs.sh stats    # show rule counts per chapter
EOF
}

cmd="${1:-verify}"

case "$cmd" in
  verify)
    total=0
    for ((d = 1; d <= CHAPTERS; d++)); do
      found="$(count_rules "$d")"
      expected="$(count_refs "$d")"
      if [[ "$found" != "$expected" ]]; then
        echo "FAIL V${d}: expected $expected, found $found"
        exit 1
      fi
      total=$((total + found))
    done
    echo "OK: rules consistent with references (total=$total, V1..V${CHAPTERS})."
    ;;
  stats)
    echo "Rules dir: $RULES_DIR"
    total=0
    for ((d = 1; d <= CHAPTERS; d++)); do
      n="$(count_rules "$d")"
      total=$((total + n))
      echo "V${d}: $n"
    done
    echo "Total: $total"
    ;;
  *)
    print_usage
    exit 2
    ;;
esac
