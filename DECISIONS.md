# MIRROR Decisions

## 2026-05-16

- Kraken trading integration uses the official `kraken` CLI through an async subprocess wrapper. The local environment does not currently have `kraken` on PATH, so verification fails clearly until installed.
- Featherless is configured as the primary Red/Blue OpenAI-compatible provider using `https://api.featherless.ai/v1`.
- Gemini is configured for Strategy Patcher/crossover calls via the official Gemini API.
- ERC-8004 expected Base Sepolia addresses were verified from the canonical repository search result and are treated as expected defaults, not blind truth.
- On-chain operations default to disabled via `ONCHAIN_ENABLED=false`; queued jobs are used when configuration is incomplete.

## 2026-05-19

- MIRROR now documents and supports two Kraken execution paths: local futures paper mode for auditable dry runs and authenticated Kraken demo-futures account mode for the deployed PnL tournament runtime. Mainnet or real-capital execution remains out of scope.
- The deployed tournament objective is net PnL. Execution controls therefore prioritize reducing repeated loss patterns and locking gains during drawdown while preserving the mock-free Kraken CLI audit trail.
- Tournament recovery take-profit is enabled by default. When the latest account equity snapshot reports net PnL below `TOURNAMENT_RECOVERY_PNL_THRESHOLD_USD`, trades that reach forecast take-profit close immediately instead of waiting for winner extension or trailing/time-stop behavior.
- The strategy field `tournament_cooldown_minutes_after_loss` is now enforced during tournament risk evaluation to block immediate same-symbol/same-direction re-entry after a realized loss.
- Agent API Basescan links are built as NFT links using the configured ERC-8004 identity registry contract plus token ID: `https://sepolia.basescan.org/nft/<identity-registry>/<token-id>`. This replaces the previous token-ID-only URL shape, which was not a reliable ERC-721 agent identity link.
- README and env examples are treated as operator-facing artifacts and must stay aligned with supported modes, tournament controls, deployment assumptions, and verification commands.
