# MIRROR Decisions

## 2026-05-16

- Kraken trading integration uses the official `kraken` CLI through an async subprocess wrapper. The local environment does not currently have `kraken` on PATH, so verification fails clearly until installed.
- Featherless is configured as the primary Red/Blue OpenAI-compatible provider using `https://api.featherless.ai/v1`.
- Gemini is configured for Strategy Patcher/crossover calls via the official Gemini API.
- ERC-8004 expected Base Sepolia addresses were verified from the canonical repository search result and are treated as expected defaults, not blind truth.
- On-chain operations default to disabled via `ONCHAIN_ENABLED=false`; queued jobs are used when configuration is incomplete.

