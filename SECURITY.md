# Security

- Never configure live trading credentials for MIRROR.
- `TRADING_ENABLED` defaults to `false`.
- Kraken paper mode is verified before any order path can execute.
- Secrets are never logged. Structured logs redact keys and private key material.
- External actions use idempotency keys or natural uniqueness constraints.

