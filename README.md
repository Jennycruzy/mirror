# MIRROR

MIRROR is a mock-free AI trading-agent system. Four Red agents trade through the official Kraken CLI in either futures paper mode or authenticated Kraken demo-futures account mode, depending on configuration. Blue agents analyze Red calibration failures. Gemini proposes strategy patches, deterministic holdout replay decides whether they survive, and promoted versions are queued or registered as ERC-8004 identities on Base Sepolia.

Calibration is the fitness function: Red agents evolve by reducing the gap between stated confidence and realized accuracy.

## What This Build Does

- Runs four Red trading agents (`red-a` through `red-d`) on a fixed cadence.
- Uses real Kraken CLI market data and execution surfaces; no fake exchange adapter exists.
- Supports local futures paper mode for auditable dry runs and authenticated Kraken demo-futures account mode for the PnL tournament runtime.
- Tracks forecasts, trades, fills, account equity, PnL, Blue findings, patches, lineage, on-chain registration jobs, and event stream data in Postgres.
- Optimizes for the lablab/Kraken PnL track through net PnL controls: trend gating, spread checks, position caps, adaptive loser blocking, loss cooldowns, profit lock, trailing exits, time stops, and recovery take-profit behavior.
- Registers ERC-8004 agent identities and posts Brier-score reputation feedback when on-chain mode and wallet/IPFS credentials are configured.

## Architecture

- Backend: FastAPI, SQLAlchemy 2 async, Alembic, Pydantic v2, LangGraph, APScheduler, structlog, httpx, web3.py, uv.
- Frontend: Next.js App Router, TypeScript strict mode, Tailwind, Recharts, D3-style SVG lineage rendering, SSE.
- Database: Postgres through Docker Compose for local development.
- Trading: official Kraken CLI only, with support for futures paper mode and authenticated demo-futures account mode.
- Inference: Featherless/OpenAI-compatible Qwen for Red/Blue, Gemini for patching and crossover.
- Identity: ERC-8004 Identity and Reputation registries on Base Sepolia.
- Metadata: IPFS pinning through configured provider.

## Safety Model

- `TRADING_ENABLED=false` by default.
- MIRROR refuses to place orders unless the configured Kraken execution mode is verified.
- In futures paper mode, xStock perpetual symbols must be discovered from real Kraken output.
- No mainnet or real-capital trading path is implemented.
- No external integration is mocked.
- Missing keys, CLIs, RPCs, or IPFS providers fail loudly through CLI checks, events, API health, and dashboard state.
- Secrets are redacted from structured logs.

## Operating Modes

MIRROR has three important mode switches:

- `TRADING_ENABLED=false`: forecasts and risk decisions are recorded, but orders are skipped.
- `TRADING_ENABLED=true`: allowed trades are placed through the configured Kraken CLI mode.
- `MIRROR_MODE=tournament`: enables tournament risk gates, PnL sizing, adaptive routing, scout behavior, and exit sweeps.

Kraken execution modes:

- `KRAKEN_EXECUTION_MODE=paper`: uses Kraken futures paper commands and xStock symbol discovery.
- `KRAKEN_EXECUTION_MODE=account`: uses authenticated futures account commands. The deployed PnL tournament runtime uses this mode against Kraken demo futures.
- `KRAKEN_EXECUTION_MODE=spot_paper`: supported by the code path for local spot-paper experiments; shorts are blocked in this mode.

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
- `KRAKEN_CLI_PATH=kraken`
- `KRAKEN_EXECUTION_MODE=paper`
- `KRAKEN_REQUIRE_PAPER_MODE=true`
- `TRADING_ENABLED=false`
- `ONCHAIN_ENABLED=false`
- `MIRROR_MODE=calibration`
- `BASE_SEPOLIA_CHAIN_ID=84532`
- `ERC8004_IDENTITY_REGISTRY=0x8004A818BFB912233c491871b3d84c89A494BD9e`
- `ERC8004_REPUTATION_REGISTRY=0x8004B663056A597Dffe9eCcC1965A193B7388713`

For authenticated Kraken demo-futures tournament mode:

- `KRAKEN_EXECUTION_MODE=account`
- `KRAKEN_REQUIRE_PAPER_MODE=false`
- `KRAKEN_FUTURES_URL=https://demo-futures.kraken.com/derivatives/api/v3`
- `KRAKEN_DANGER_ALLOW_ANY_URL_HOST=true`
- `KRAKEN_API_KEY=<read/write demo key>`
- `KRAKEN_API_SECRET=<demo secret>`
- `TRADING_ENABLED=true`
- `MIRROR_MODE=tournament`

Tournament PnL controls:

- `TOURNAMENT_ADAPTIVE_ENABLED=true`
- `TOURNAMENT_ADAPTIVE_LOOKBACK_TRADES=6`
- `TOURNAMENT_ADAPTIVE_MIN_SAMPLES=2`
- `TOURNAMENT_ADAPTIVE_DISABLE_LOSS_USD=0.0`
- `TOURNAMENT_MAX_POSITION_RISK_PCT=3`
- `TOURNAMENT_MAX_CONCURRENT_POSITIONS=3`
- `TOURNAMENT_MAX_SAME_SIDE_SYMBOL_POSITIONS=1`
- `TOURNAMENT_SCOUT_EQUITY_PCT=4`
- `TOURNAMENT_AGGRESSIVE_EQUITY_PCT=12`
- `TOURNAMENT_MAX_SYMBOL_EXPOSURE_PCT=25`
- `TOURNAMENT_MIN_TREND_BPS=8`
- `TOURNAMENT_SYMBOL_SPREAD_CAPS=PI_XBTUSD:10,PI_ETHUSD:12,PI_XRPUSD:25,PI_LTCUSD:25,PI_BCHUSD:35,PF_SOLUSD:250`
- `TOURNAMENT_PROFIT_LOCK_PCT=0.35`
- `TOURNAMENT_TRAILING_GIVEBACK_PCT=0.18`
- `TOURNAMENT_MIN_HOLD_SECONDS=45`
- `TOURNAMENT_WINNER_EXTENSION_MINUTES=180`
- `TOURNAMENT_RECOVERY_TAKE_PROFIT_ENABLED=true`
- `TOURNAMENT_RECOVERY_PNL_THRESHOLD_USD=0.0`
- `TOURNAMENT_EQUITY_SNAPSHOT_MIN_SECONDS=300`

Recovery take-profit means that when the latest account equity snapshot reports net PnL below `TOURNAMENT_RECOVERY_PNL_THRESHOLD_USD`, trades that reach their forecast take-profit close immediately instead of waiting for the trailing/time-stop path. This is intended for clawing back a negative PnL without disabling the existing winner-extension behavior when the account is at or above breakeven.

## Verify

Run all preflight checks:

```bash
cd backend
uv run mirror verify
```

`mirror verify` checks Python, Postgres, Kraken CLI, the configured Kraken execution mode, the configured futures symbol universe or paper-mode symbol discovery path, Featherless, Gemini, Base Sepolia, ERC-8004 ABIs/addresses, and frontend environment.

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

`discover-symbols` fails if fewer than three xStock perpetual symbols are found from real Kraken ticker output. This command is primarily for the futures paper discovery path; production tournament mode can also run against an explicitly configured futures symbol universe.

## Run

Run one Red:

```bash
uv run mirror run --once --agent red-a
```

Run scheduler:

```bash
uv run mirror run --scheduler
```

The scheduler runs:

- Red forecasts every 30 minutes.
- Resolution sweep every 1 minute.
- Blue scans every 4 hours.
- Scout-floor check every 1 hour.
- Tournament exit sweep every `TOURNAMENT_EXIT_CHECK_SECONDS`.

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

Inspect current local state:

```bash
uv run mirror status
uv run mirror backtest --agent red-a
uv run mirror smoke
```

Force one exit-management pass:

```bash
uv run mirror run exits
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
- Account equity, realized and unrealized PnL, open trade counts, and closed fill counts from Kraken trading status.
- Interactive portfolio/orders table with side and status filters plus per-trade detail expansion.
- Stream/poll merge logic that reloads persisted events and guards degraded backend states instead of blank rendering.

Useful API routes:

- `GET /health`
- `GET /agents`
- `GET /trades`
- `GET /trades/paper-status`
- `GET /events`
- `GET /stream`
- `GET /forecasts`
- `GET /patches`
- `GET /onchain-jobs`

Frontend environment:

- Browser API base: `NEXT_PUBLIC_BACKEND_URL`
- Server-side API base override: `BACKEND_INTERNAL_URL`
- Local default: frontend proxies through `/api`

## PnL Track Notes

For the lablab/Kraken Trading Performance track, ranking is based on net PnL over the competition period. MIRROR therefore treats PnL protection as an execution concern, separate from ERC-8004 reputation:

- Position size is capped by account equity, configured risk percentage, leverage, and per-symbol exposure.
- Low confidence trades above scout size are vetoed.
- Longs/shorts must pass trend direction checks when trend data is available.
- Excessive spreads are vetoed by symbol-specific caps.
- Only one same-side position per symbol is open by default.
- Recently losing symbol/direction pairs are adaptively blocked after enough samples.
- A same-symbol/same-direction loss cooldown prevents immediate revenge entries.
- Exit sweeps enforce stop-loss, trailing profit lock, time-stop, winner extension, and recovery take-profit.

Positive PnL is not guaranteed. These controls reduce repeated loss patterns and lock gains sooner during drawdown while preserving the mock-free exchange and audit trail.

## Recent Changes

The README now tracks the latest shipped changes in `main` so operators do not need to reconstruct behavior from commit history.

- `Add PnL recovery controls`
  - Recovery take-profit closes winning trades at forecast take-profit while account net PnL is below the configured threshold.
  - Same-symbol/same-direction loss cooldown now enforces the strategy's `tournament_cooldown_minutes_after_loss`.
  - Tournament tests cover both recovery exits and cooldown vetoes.
- `Repair onchain registration and exit recovery`
  - Failed `register_agent` jobs are re-queued with rebuilt parent and crossover lineage metadata instead of remaining stuck failed.
  - Registration now preserves a successful mint if `setAgentURI` reverts: MIRROR stores the minted token, keeps the provisional IPFS URI, and records the URI mutation error on the event.
  - Tournament exit sweeps now degrade cleanly on Kraken status or ticker failures, emit warning events, and continue the scheduler rather than crashing the run loop.
  - Kraken exit orders use stable idempotency keys and the activity feed surfaces these degraded execution/on-chain states.
- `Add interactive terminal controls`
  - The trading terminal now exposes clickable trade rows, filter chips for side and order status, and inline execution details for the selected trade.
  - Dashboard panels and feeds were adjusted to support higher-information terminal monitoring without leaving the main screen.
- `Polish Mirror trading terminal UI`
  - The terminal layout, gradients, panel chrome, and typography were refined for the current dashboard presentation.
  - Activity, battalion, Blue findings, patch queue, on-chain queue, and position views were restyled to keep the trading view readable under live refresh.
- `Add adaptive tournament direction routing`
  - Tournament routing can disable a losing symbol/direction pair after enough recent samples and sustained negative realized PnL.
  - Symbol selection can rank markets by recent realized PnL, so stronger recent directions are favored rather than using only static ordering.
  - Adaptive routing is controlled through the `TOURNAMENT_ADAPTIVE_*` settings listed above.
- `Optimize tournament PnL execution`
  - Exit management records periodic account equity snapshots and uses them in the event stream for portfolio monitoring.
  - Trades now support profit-lock and trailing-giveback exits in addition to stop-loss and time-stop handling.
  - Winning trades can stay open beyond the base resolution time for a bounded extension window.
- `Fix dashboard API base and render guards`
  - Frontend API and SSE helpers were corrected to honor the configured backend base consistently.
  - Dashboard components now fail soft when partial backend data is unavailable, which reduces broken terminal renders during startup or degraded runs.

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

Use managed Postgres for persistence. Do not enable `TRADING_ENABLED=true` until `mirror verify` passes and the selected Kraken execution mode is confirmed.

## Live Deployment

Production is currently deployed on the VPS at `130.61.38.218` and served at:

- `https://mirrorlabs.duckdns.org`

Verified live production state:

- nginx terminates TLS for `mirrorlabs.duckdns.org` with a valid Let's Encrypt certificate and redirects HTTP to HTTPS.
- The Mirror frontend is served behind nginx and the backend API is proxied to the live FastAPI service.
- Postgres is running on the VPS and the live backend health endpoint reports Postgres healthy.
- PM2 manages the live `mirror-api`, `mirror-scheduler`, and `mirror-frontend` processes.
- The live trading runtime uses authenticated Kraken demo-futures account mode, not `kraken futures paper`.
- Production Kraken settings were verified on the VPS with `KRAKEN_EXECUTION_MODE=account`, `KRAKEN_REQUIRE_PAPER_MODE=false`, and `KRAKEN_FUTURES_URL=https://demo-futures.kraken.com/derivatives/api/v3`.
- The current deployed futures symbol universe is explicitly configured as `PI_XBTUSD`, `PI_ETHUSD`, and `PI_XRPUSD`.
- `mirror verify` passes on the VPS for Python, Postgres, Kraken CLI, Kraken execution mode, configured symbol universe, Featherless, Base Sepolia connectivity, ERC-8004 addresses/ABIs, and frontend environment.
- Base Sepolia connectivity is confirmed against chain ID `84532`.
- Live event and equity snapshot data are present in production.
- The legacy `geotruth` deployment and nginx vhost were removed from the VPS.

## Tests

Run focused tournament tests:

```bash
cd backend
uv run pytest tests/test_tournament.py tests/test_tournament_exits.py
```

Run the full backend suite:

```bash
cd backend
uv run pytest tests
```

Current local verification after the PnL recovery changes:

- `tests/test_tournament.py tests/test_tournament_exits.py`: 17 passed.
- `tests`: 53 passed.

## Demo

```bash
./scripts/demo.sh
```

The script prints the operator sequence and current status. It does not fake trades or data.

## Current Limitations

- Full live verification described above applies to the deployed VPS environment, not automatically to every local machine cloning this repo.
- Local development still requires real credentials, reachable Postgres, Kraken CLI access, inference keys, and chain/IPFS configuration before `mirror verify` and end-to-end flows will pass.
- There are two materially different Kraken paths in this project: futures paper mode for local auditable paper verification and xStock discovery, and authenticated demo-futures account mode for the deployed tournament runtime.
- Production verification does not imply that a fresh local machine will pass the paper-mode xStock discovery checks unless that machine is configured for the paper workflow.
- The checked-in repo `.env` may remain empty on development machines or servers if runtime secrets are injected through the process manager instead of being committed to disk.
- Other applications may coexist on the VPS, but MIRROR now owns the `mirrorlabs.duckdns.org` hostname and TLS configuration.

## Troubleshooting

- Kraken missing: install official CLI and ensure `KRAKEN_CLI_PATH` points to it.
- Postgres connection refused: run `docker compose up -d postgres`.
- xStock discovery fails: confirm Kraken futures paper tickers expose xStock perpetual symbols.
- Inference fails: set `FEATHERLESS_API_KEY` or `GEMINI_API_KEY`.
- On-chain jobs fail: check `BASE_SEPOLIA_RPC_URL`, wallet funding, `PINATA_JWT`, and `ONCHAIN_ENABLED`.
- Dashboard empty: confirm backend is running and Postgres contains agents/events.
- PnL remains negative: confirm `MIRROR_MODE=tournament`, scheduler is running, exit sweeps are firing, `account_equity_snapshot` events are present, and adaptive/cooldown vetoes are visible in the event tape.
- Recovery take-profit not triggering: confirm the latest `account_equity_snapshot.payload_json.net_pnl` is below `TOURNAMENT_RECOVERY_PNL_THRESHOLD_USD` and `TOURNAMENT_RECOVERY_TAKE_PROFIT_ENABLED=true`.
