#!/usr/bin/env bash
# Mock test of this Account's rendered SQL (01, 02, 03, 04, 99) on a throw-away local PostgreSQL 16.
# Usage: bash accounts/<account>/tests/run_mock_test.sh <original clinic csv>
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
exec bash "$HERE/../../tools/legacy_mock/run_mock_test.sh" "$HERE" "$1"
