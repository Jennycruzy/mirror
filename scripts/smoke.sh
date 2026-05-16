#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT/backend"
uv run pytest
uv run python -m compileall mirror tests
uv run mirror smoke

cd "$ROOT"
pnpm --filter mirror-frontend build

