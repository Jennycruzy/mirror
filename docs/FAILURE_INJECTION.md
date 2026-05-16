# Failure Injection

These checks verify MIRROR fails honestly instead of hiding missing dependencies.

## Remove Featherless key

Unset `FEATHERLESS_API_KEY` and run:

```bash
cd backend
uv run mirror verify
```

Expected: Featherless check fails. Red/Blue calls require Gemini fallback if configured; otherwise they fail with setup instructions.

## Break Base Sepolia RPC

Set `BASE_SEPOLIA_RPC_URL=http://127.0.0.1:1` and run:

```bash
uv run mirror verify
uv run mirror onchain retry
```

Expected: Base Sepolia verification fails and on-chain jobs remain failed/queued with visible errors.

## Kill scheduler

Stop `mirror run --scheduler`, then run:

```bash
uv run mirror status
```

Expected: persisted events/forecasts remain visible. Restarting the scheduler resumes interval jobs.

## Force Kraken CLI error

Set `KRAKEN_CLI_PATH=/not/found/kraken` and run:

```bash
uv run mirror verify
```

Expected: Kraken installed, paper mode, and xStock discovery checks fail. Trading remains blocked.

