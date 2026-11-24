#!/usr/bin/env bash
# API smoke with mock IRC (no live network). See RELEASE-1.0.0.md matrix.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export BOOKPUP_IRC_MOCK=1
export BOOKPUP_XDCC_MOCK=1
exec python3 -m unittest \
  tests.test_smoke_api tests.test_server_public tests.test_auth tests.test_sideload \
  tests.test_kindle_smtp tests.test_walk_trail tests.test_walk_trail_steps \
  tests.test_ops_readiness tests.test_e2e_flow -v