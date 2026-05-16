# MIRROR

MIRROR is a mock-free AI trading-agent system. Four Red agents trade Kraken paper xStock perpetual futures. Blue agents analyze Red calibration failures. Gemini proposes strategy patches, deterministic holdout replay decides whether they survive, and promoted versions are queued or registered as ERC-8004 identities on Base Sepolia.

Calibration is the fitness function: Red agents evolve by reducing the gap between stated confidence and realized accuracy.

## Architecture

- Backend: FastAPI, SQLAlchemy 2 async, Alembic, Pydantic v2, LangGraph, APScheduler, structlog, httpx, web3.py, uv.
- Frontend: Next.js App Router, TypeScript strict mode, Tailwind, Recharts, D3-style SVG lineage rendering, SSE.
- Database: Postgres through Docker Compose for local development.
- Trading: official Kraken CLI only, paper mode only.
- Inference: Featherless/OpenAI-compatible Qwen for Red/Blue, Gemini for patching and crossover.
- Identity: ERC-8004 Identity and Reputation registries on Base Sepolia.
- Metadata: IPFS pinning through configured provider.

## Safety Model

- `TRADING_ENABLED=false` by default.
- MIRROR refuses to place orders unless Kraken paper mode is verified.
- xStock perpetual symbols must be discovered from real Kraken output.
- No live trading path is implemented.
- No external integration is mocked.
- Missing keys, CLIs, RPCs, or IPFS providers fail loudly through CLI checks, events, API health, and dashboard state.
- Secrets are redacted from structured logs.

## Setup

Install backend dependencies:

```bash
cd backend
uv sync
```

Install frontend dependencies:

```bash
cd ..
pnpm install
```

Start Postgres:

```bash
docker compose up -d postgres
```

Configure environment:

```bash
cp .env.example .env
```

Install the official Kraken CLI:

```bash
cargo install --git https://github.com/krakenfx/kraken-cli
```

## Environment

Required variables are documented in `.env.example`. Important defaults:

- `DATABASE_URL=postgresql+asyncpg://mirror:mirror@localhost:5432/mirror`
- `TRADING_ENABLED=false`
- `ONCHAIN_ENABLED=false`
- `BASE_SEPOLIA_CHAIN_ID=84532`
- `ERC8004_IDENTITY_REGISTRY=0x8004A818BFB912233c491871b3d84c89A494BD9e`
- `ERC8004_REPUTATION_REGISTRY=0x8004B663056A597Dffe9eCcC1965A193B7388713`

## Verify

Run all preflight checks:

```bash
cd backend
uv run mirror verify
```

`mirror verify` checks Python, Postgres, Kraken CLI, Kraken paper mode, xStock discovery, Featherless, Gemini, Base Sepolia, ERC-8004 ABIs/addresses, and frontend environment.

Run local smoke checks that do not require live external success:

```bash
../scripts/smoke.sh
```

## Initialize

```bash
cd backend
uv run mirror init
uv run mirror discover-symbols
```

`discover-symbols` fails if fewer than three xStock perpetual symbols are found from real Kraken ticker output.

## Run

Run one Red:

```bash
uv run mirror run --once --agent red-a
```

Run scheduler:

```bash
uv run mirror run --scheduler
```

Run resolution sweep:

```bash
uv run mirror run resolve
```

Run Blue scan:

```bash
uv run mirror run blue-scan --agent red-a
```

Request a patch from a real Blue finding:

```bash
uv run mirror patch --agent red-a --finding <finding-id>
```

Attempt crossover from an accepted patch:

```bash
uv run mirror crossover --patch <patch-id>
```

Queue/register agents:

```bash
uv run mirror register-agents
uv run mirror onchain retry
```

## Dashboard

Start backend:

```bash
cd backend
uv run uvicorn mirror.api.main:app --reload
```

Start frontend:

```bash
cd frontend
pnpm dev
```

Open `http://localhost:3000`.

Dashboard claims come from API/Postgres:

- Forecast/trade/patch/crossover counts.
- Red version, status, token state, latest forecast, rolling Brier, trade floor.
- Blue findings.
- On-chain queue.
- SSE activity feed.
- Lineage graph with vertical and crossover edges.

## ERC-8004

Canonical source: `https://github.com/erc-8004/erc-8004-contracts`

Copied verified artifacts:

- `backend/abis/IdentityRegistry.json`
- `backend/abis/ReputationRegistry.json`
- `backend/abis/ValidationRegistry.json`
- `docs/ERC8004SPEC.md`
- `docs/ERC8004_ADDRESSES.md`

Base Sepolia:

- Identity Registry: `0x8004A818BFB912233c491871b3d84c89A494BD9e`
- Reputation Registry: `0x8004B663056A597Dffe9eCcC1965A193B7388713`

Identity registration pins provisional metadata, mints with `register(string)`, pins final metadata with the token ID, then calls `setAgentURI` when enabled and configured.

Reputation feedback uses:

- `value = int(brier_score * 10000)`
- `valueDecimals = 4`
- `tag1 = "mirror.brier"`

Self-feedback is avoided by requiring an evaluator wallet separate from the owner wallet.

## Reset

Reset is destructive and guarded:

```bash
cd backend
uv run mirror reset --confirm
```

This drops and recreates database tables. It does not touch external systems.

## Failure Injection

See `docs/FAILURE_INJECTION.md`.

## Deployment Notes

Backend can deploy to Railway, Fly.io, Render, or Vultr with:

- Python 3.11+
- Postgres
- `uv run uvicorn mirror.api.main:app --host 0.0.0.0 --port $PORT`
- Real `.env` values

Frontend can deploy to Vercel with:

- `NEXT_PUBLIC_BACKEND_URL=<backend-url>`
- `pnpm build`

Use managed Postgres for persistence. Do not enable `TRADING_ENABLED=true` until `mirror verify` passes and Kraken paper mode is confirmed.

## Demo

```bash
./scripts/demo.sh
```

The script prints the operator sequence and current status. It does not fake trades or data.

## Current Limitations

- Full end-to-end live acceptance requires configured Kraken CLI paper credentials, real xStock availability, Postgres, inference keys, IPFS credentials, Base Sepolia RPC, and funded owner/evaluator wallets.
- The local environment used for this build did not have Kraken CLI or Postgres running, so live trading/resolution/minting were not executed.
- Kraken order placement remains fail-closed until the local official CLI order surface is verified with installed `kraken --help`.
- Screenshots are not included because no live dashboard data was available locally.

## Troubleshooting

- Kraken missing: install official CLI and ensure `KRAKEN_CLI_PATH` points to it.
- Postgres connection refused: run `docker compose up -d postgres`.
- xStock discovery fails: confirm Kraken futures paper tickers expose xStock perpetual symbols.
- Inference fails: set `FEATHERLESS_API_KEY` or `GEMINI_API_KEY`.
- On-chain jobs fail: check `BASE_SEPOLIA_RPC_URL`, wallet funding, `PINATA_JWT`, and `ONCHAIN_ENABLED`.
- Dashboard empty: confirm backend is running and Postgres contains agents/events.

