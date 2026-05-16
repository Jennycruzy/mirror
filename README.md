# MIRROR

MIRROR is an AI trading-agent system where Red agents trade Kraken paper xStock perpetual futures and Blue agents search for Red calibration failures. Accepted strategy patches are gated by holdout Brier improvement and trade-rate preservation before new agent versions are registered on ERC-8004.

This repository is intentionally mock-free. If Kraken CLI, Postgres, inference keys, IPFS, or Base Sepolia access are missing, commands fail with setup instructions instead of substituting fake data.

## Quick Start

1. Install dependencies:
   ```bash
   cd backend
   uv sync
   ```
2. Start Postgres:
   ```bash
   docker compose up -d postgres
   ```
3. Copy environment:
   ```bash
   cp .env.example .env
   ```
4. Install Kraken CLI from the official repository:
   ```bash
   cargo install --git https://github.com/krakenfx/kraken-cli
   ```
5. Verify:
   ```bash
   uv run mirror verify
   ```

`TRADING_ENABLED=false` by default. Even when enabled, MIRROR refuses to trade unless Kraken paper mode is verified and symbols are discovered from real Kraken output.

## Day 1 Status

Implemented:

- Repository scaffold.
- Async SQLAlchemy models and initial Alembic migration.
- Strategy YAML schema with locked-field patch rejection.
- Brier math and holdout gate.
- Typed Kraken CLI wrapper using subprocess JSON parsing.
- Featherless and Gemini real HTTP clients with strict JSON parsing.
- Minimal Red forecast flow that stores forecasts and only places paper trades after verification.
- CLI commands: `verify`, `init`, `init agents`, `discover-symbols`, `run --once --agent`, `status`.

External systems are not mocked. Missing services appear as failed verification checks and structured events.

