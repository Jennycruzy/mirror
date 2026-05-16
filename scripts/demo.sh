#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cat <<'TEXT'
MIRROR demo flow

This script prints the operator sequence. It does not bypass verification,
does not enable trading, and does not invent external data.
TEXT

cat <<'TEXT'

1. Start Postgres:
   docker compose up -d postgres

2. Configure .env from .env.example with real Kraken paper, inference, IPFS, and Base Sepolia settings.

3. Verify:
   cd backend && uv run mirror verify

4. Initialize:
   uv run mirror init
   uv run mirror discover-symbols

5. Run one Red:
   uv run mirror run --once --agent red-a

6. Run scheduler:
   uv run mirror run --scheduler

7. Open dashboard:
   cd ../frontend && pnpm dev
TEXT

cd "$ROOT/backend"
uv run mirror status || true

