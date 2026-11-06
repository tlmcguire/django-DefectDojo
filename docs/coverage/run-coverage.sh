#!/usr/bin/env bash
# Run the unit test suite under coverage.py and write reports to docs/coverage/<label>/.
#
# Mirrors the three phases in docker/entrypoint-unit-tests.sh (parallel, non-parallel,
# transactional; performance tests excluded) so the measured suite is the one CI runs.
# Expects a migrated PostgreSQL test database and the DD_* environment of
# docker-compose.override.unit_tests.yml already exported.
#
# Usage: docs/coverage/run-coverage.sh baseline
set -u

label="${1:?usage: $0 <label>}"
here="$(cd "$(dirname "$0")" && pwd)"
rc="$here/.coveragerc"
out="$here/$label"
data="${COVERAGE_DATA_DIR:-$(mktemp -d)}"

mkdir -p "$out"
export COVERAGE_FILE="$data/.coverage"
export COVERAGE_PROCESS_START="$rc"

status=0
run() {
    coverage run --rcfile="$rc" manage.py test unittests --keepdb --no-input "$@" || status=1
}
run --parallel="${DD_TEST_PARALLEL:-auto}" --exclude-tag=non-parallel --exclude-tag=transactional --exclude-tag=performance
run --tag=non-parallel --exclude-tag=performance
run --tag=transactional --exclude-tag=performance

coverage combine --rcfile="$rc" -q "$data"
coverage report --rcfile="$rc" > "$out/report.txt"
coverage json --rcfile="$rc" -q -o "$out/coverage.json"
tail -n 1 "$out/report.txt"
exit "$status"
