#!/usr/bin/env bash
# ── Full Verification Harness ─────────────────────────────────────────
# Runs all three tiers: spec verification, Python tests, and frontend tests.
#
# Usage:
#   bash scripts/verify-all.sh           # Run all checks
#   bash scripts/verify-all.sh --update  # Update spec manifest first, then verify
#
# Exit codes:
#   0 = All checks passed
#   1 = One or more checks failed

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAILED=0

echo "============================================================"
echo "  PROJECT MUSHROOM CLOUD — FULL VERIFICATION"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""

# ── Tier 1: Spec Verification ──
echo "── TIER 1: Spec Verification ──────────────────────────────"
if [[ "${1:-}" == "--update" ]]; then
    echo "  (updating manifest first)"
    cd "$ROOT" && npx tsx scripts/verify-spec.ts --update
    echo ""
fi

if cd "$ROOT" && npx tsx scripts/verify-spec.ts; then
    echo ""
else
    echo "  !! Spec verification FAILED"
    FAILED=1
    echo ""
fi

# ── Tier 2: Python Tests ──
echo "── TIER 2: Python Tests ───────────────────────────────────"
if cd "$ROOT" && python -m pytest tests/ -q --ignore=tests/test_api.py --ignore=tests/test_api_cases.py --tb=short 2>&1; then
    echo ""
else
    echo "  !! Python tests FAILED"
    FAILED=1
    echo ""
fi

# ── Tier 3: Frontend Tests ──
echo "── TIER 3: Frontend Unit Tests ────────────────────────────"
if cd "$ROOT/frontend" && npx vitest run 2>&1; then
    echo ""
else
    echo "  !! Frontend tests FAILED"
    FAILED=1
    echo ""
fi

# ── Summary ──
echo "============================================================"
if [[ $FAILED -eq 0 ]]; then
    echo "  ALL TIERS PASSED"
else
    echo "  SOME TIERS FAILED — see output above"
fi
echo "============================================================"

exit $FAILED
