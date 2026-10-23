#!/usr/bin/env bash
# End-to-end smoke test against the registration service (which calls the course service).
# Usage: BASE_URL=http://localhost:5000 ./scripts/smoke-test.sh
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:5000}"
fail() { echo "FAIL: $*" >&2; exit 1; }

echo "==> GET /health"
curl -fsS "$BASE_URL/health" | grep -q '"status":"ok"' || fail "health check"

echo "==> GET /courses (registration -> course)"
curl -fsS "$BASE_URL/courses" | grep -q 'CS01' || fail "course list did not contain CS01"

echo "==> POST /register (valid course)"
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE_URL/register" \
  -H 'Content-Type: application/json' -d '{"user":"smoke-test","course_id":"CS01"}')
[ "$code" = "201" ] || fail "expected 201, got $code"

echo "==> POST /register (unknown course)"
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE_URL/register" \
  -H 'Content-Type: application/json' -d '{"user":"smoke-test","course_id":"NOPE"}')
[ "$code" = "404" ] || fail "expected 404, got $code"

echo "==> GET /registrations"
curl -fsS "$BASE_URL/registrations" | grep -q 'smoke-test' || fail "registration not stored"

echo "All smoke tests passed."
