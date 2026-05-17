# External Interface Verification

Verification performed on 2026-05-16 and refreshed on 2026-05-17.

## Kraken CLI

Official repository: `https://github.com/krakenfx/kraken-cli`

Verified from the canonical repository listing:

- Install command: `cargo install --git https://github.com/krakenfx/kraken-cli`
- Ticker command surfaced by docs: `kraken futures tickers`
- Futures paper status: `kraken futures paper status -o json`
- Futures paper balance: `kraken futures paper balance -o json`
- Futures paper initialization: `kraken futures paper init -o json`
- Futures paper market buy: `kraken futures paper buy <SYM> <SIZE> --leverage <L> --type market --client-order-id <ID> -o json`
- Futures paper market sell: `kraken futures paper sell <SYM> <SIZE> --leverage <L> --type market --client-order-id <ID> -o json`
- Successful futures paper JSON responses include `mode: "futures_paper"`.
- Verified on the VPS on 2026-05-17 with `kraken --help`, `kraken futures --help`, `kraken futures paper --help`, and live `kraken futures tickers -o json`.
- Verified xStock futures paper symbols include `PF_AAPLXUSD`, `PF_NVDAXUSD`, `PF_QQQXUSD`, `PF_SPYXUSD`, and `PF_TSLAXUSD`.

## ERC-8004

Official repository: `https://github.com/erc-8004/erc-8004-contracts`

Verified from a local clone of the canonical repository on 2026-05-16.

Copied artifacts:

- `backend/abis/IdentityRegistry.json`
- `backend/abis/ReputationRegistry.json`
- `backend/abis/ValidationRegistry.json`
- `docs/ERC8004SPEC.md`
- `docs/ERC8004_ADDRESSES.md`

Verified Base Sepolia addresses:

- IdentityRegistry: `0x8004A818BFB912233c491871b3d84c89A494BD9e`
- ReputationRegistry: `0x8004B663056A597Dffe9eCcC1965A193B7388713`

Verified function signatures from ABI/spec:

- Identity `register(string agentURI) returns (uint256 agentId)`
- Identity `register() returns (uint256 agentId)`
- Identity `setAgentURI(uint256 agentId, string newURI)`
- Reputation `giveFeedback(uint256 agentId, int128 value, uint8 valueDecimals, string tag1, string tag2, string endpoint, string feedbackURI, bytes32 feedbackHash)`

Repository docs state the normative spec is `ERC8004SPEC.md`, Identity Registry is ERC-721 based, `register` mints an agent NFT, and `setAgentURI` can update agent URI. Reputation Registry prevents self-feedback.

## Featherless

Docs: `https://featherless.ai/docs`

Verified:

- API is OpenAI compatible.
- Base URL: `https://api.featherless.ai/v1`
- Quickstart uses OpenAI-compatible chat completions and Qwen model examples such as `Qwen/Qwen2.5-7B-Instruct`.
- JSON mode support must be verified against the configured model. MIRROR therefore validates JSON with Pydantic and retries instead of assuming native JSON mode.

## Gemini

Docs: `https://ai.google.dev/gemini-api/docs`

Configured model default is `gemini-3-pro`; `mirror verify` checks the configured API key/model and fails clearly if unavailable.

## LangGraph

Docs: `https://docs.langchain.com/oss/python/langgraph/graph-api` and LangChain reference.

Verified import:

```python
from langgraph.graph import StateGraph
```
