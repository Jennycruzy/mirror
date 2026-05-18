import pytest

from mirror.clients.kraken import KrakenClient, KrakenCommandResult, extract_price_for_symbol, extract_spot_price, extract_xstock_perp_symbols, format_cli_number, futures_order_size, is_xstock_perp_symbol, normalize_account_status, select_best_xstock_record, spot_ticker_record, validate_order_response
from mirror.config import Settings
from mirror.errors import KrakenCliCommandFailed


class RecordingKrakenClient(KrakenClient):
    def __init__(self, settings: Settings, responses: list[object] | None = None, failures: set[tuple[str, ...]] | None = None):
        super().__init__(settings)
        self.responses = responses or []
        self.failures = failures or set()
        self.calls: list[list[str]] = []

    async def run_json(self, args: list[str], timeout: float | None = None) -> KrakenCommandResult:
        self.calls.append(args)
        if tuple(args) in self.failures:
            raise KrakenCliCommandFailed("planned failure")
        payload = self.responses.pop(0) if self.responses else {"mode": "futures_paper"}
        return KrakenCommandResult(args=["kraken", *args], stdout="{}", stderr="", json_data=payload)


def test_format_cli_number_removes_trailing_zeroes():
    assert format_cli_number(75.0) == "75"
    assert format_cli_number(75.125) == "75.125"


@pytest.mark.asyncio
async def test_verify_paper_mode_initializes_when_status_missing():
    client = RecordingKrakenClient(
        Settings(kraken_require_paper_mode=True),
        responses=[{"mode": "futures_paper", "initialized": True}, {"mode": "futures_paper", "available_margin": 10000}],
        failures={("futures", "paper", "status", "-o", "json")},
    )

    payload = await client.verify_paper_mode()

    assert payload["status"]["initialized"] is True
    assert client.calls == [
        ["futures", "paper", "status", "-o", "json"],
        ["futures", "paper", "init", "-o", "json"],
        ["futures", "paper", "balance", "-o", "json"],
    ]


@pytest.mark.asyncio
async def test_place_paper_order_uses_futures_paper_namespace():
    client = RecordingKrakenClient(
        Settings(kraken_require_paper_mode=True),
        responses=[
            {"mode": "futures_paper", "positions": 0},
            {"mode": "futures_paper", "available_margin": 10000},
            {"tickers": [{"symbol": "PF_TESTX_PERP", "last": "25"}]},
            {"mode": "futures_paper", "order_id": "fp-test"},
        ],
    )

    response = await client.place_paper_order("PF_TESTX_PERP", "buy", 75.0, 2, "idem-1")

    assert response["order_id"] == "fp-test"
    assert client.calls[-1] == [
        "futures",
        "paper",
        "buy",
        "PF_TESTX_PERP",
        "3",
        "--leverage",
        "2",
        "--type",
        "market",
        "--client-order-id",
        "idem-1",
        "-o",
        "json",
    ]


@pytest.mark.asyncio
async def test_place_paper_order_rejects_invalid_side_before_cli_call():
    client = RecordingKrakenClient(Settings())

    with pytest.raises(KrakenCliCommandFailed):
        await client.place_paper_order("PF_TESTX_PERP", "hold", 75.0, 2, "idem-1")

    assert client.calls == []


@pytest.mark.asyncio
async def test_place_spot_paper_order_uses_spot_paper_namespace():
    client = RecordingKrakenClient(
        Settings(kraken_execution_mode="spot_paper", kraken_require_paper_mode=True),
        responses=[
            {"mode": "paper"},
            {"mode": "paper", "USD": 10000},
            {"BTC/USD": {"c": ["50000.0"]}},
            {"mode": "paper", "order_id": "paper-1"},
        ],
    )

    response = await client.place_order("BTC/USD", "buy", 500.0, 1, "idem-spot")

    assert response["order_id"] == "paper-1"
    assert response["client_order_id"] == "idem-spot"
    assert client.calls[-1] == ["paper", "buy", "BTC/USD", "0.01", "--type", "market", "-o", "json"]


@pytest.mark.asyncio
async def test_discover_symbols_does_not_treat_crypto_suffix_x_as_xstock():
    client = RecordingKrakenClient(
        Settings(),
        responses=[{"tickers": [{"symbol": "PF_AVAXUSD", "pair": "AVAX:USD"}, {"symbol": "PF_GMXUSD", "pair": "GMX:USD"}]}],
    )

    with pytest.raises(Exception):
        await client.discover_xstock_perp_symbols()


def test_xstock_symbol_detection_matches_kraken_futures_symbols():
    assert is_xstock_perp_symbol("PF_AAPLXUSD")
    assert is_xstock_perp_symbol("PF_NVDAXUSD")
    assert not is_xstock_perp_symbol("PF_XBTUSD")


def test_xstock_extraction_uses_pair_context_to_exclude_crypto():
    payload = {
        "tickers": [
            {"symbol": "PF_AAPLXUSD", "pair": "AAPLx:USD", "last": 299},
            {"symbol": "PF_AVAXUSD", "pair": "AVAX:USD", "last": 9},
            {"symbol": "PF_SPYXUSD", "pair": "SPYx:USD", "last": 740},
        ]
    }

    assert extract_xstock_perp_symbols(payload) == ["PF_AAPLXUSD", "PF_SPYXUSD"]


def test_spot_ticker_record_extracts_price_change_and_quote_volume():
    payload = {
        "BTC/USD": {
            "a": ["76740.0", "1", "1.0"],
            "b": ["76730.0", "1", "1.0"],
            "c": ["76736.2", "0.1"],
            "o": "77410.1",
            "p": ["76956.4", "77572.7"],
            "v": ["418.4", "1386.2"],
        }
    }

    assert extract_spot_price(payload, "BTC/USD") == 76736.2
    record = spot_ticker_record(payload, "BTC/USD")
    assert record["symbol"] == "BTC/USD"
    assert record["bid"] == 76730.0
    assert record["ask"] == 76740.0
    assert record["change24h"] < 0
    assert record["volumeQuote"] > 100_000


def test_select_best_xstock_record_prefers_move_volume_and_spread():
    payload = {
        "tickers": [
            {"symbol": "PF_AAPLXUSD", "pair": "AAPLx:USD", "markPrice": 300, "bid": 299, "ask": 301, "change24h": 0.2, "volumeQuote": 1_000_000},
            {"symbol": "PF_NVDAXUSD", "pair": "NVDAx:USD", "markPrice": 400, "bid": 399.9, "ask": 400.1, "change24h": 1.5, "volumeQuote": 2_000_000},
        ]
    }

    selected = select_best_xstock_record(payload, ["PF_AAPLXUSD", "PF_NVDAXUSD"])
    assert selected is not None
    assert selected.symbol == "PF_NVDAXUSD"


def test_extract_price_for_symbol_uses_futures_mark_price_case_insensitively():
    payload = {"tickers": [{"symbol": "PI_XBTUSD", "markPrice": "77250.5"}]}
    assert extract_price_for_symbol(payload, "pi_xbtusd") == 77250.5


def test_normalize_account_status_extracts_flex_equity_and_positions():
    payload = {
        "status": {"mode": "account"},
        "accounts": {
            "accounts": {
                "flex": {
                    "portfolioValue": "20655.67",
                    "totalUnrealized": "-12.34",
                    "availableMargin": "20000",
                    "collateralValue": "20500",
                }
            }
        },
        "positions": {"openPositions": [{"symbol": "PI_XBTUSD"}]},
    }

    normalized = normalize_account_status(payload)

    assert normalized["status"]["equity"] == 20655.67
    assert normalized["status"]["pnl"] == -12.34
    assert normalized["status"]["available_margin"] == 20000.0
    assert normalized["positions"]["positions"] == [{"symbol": "PI_XBTUSD"}]


def test_futures_order_size_uses_integer_contracts_for_inverse_perps():
    instruments = {"instruments": [{"symbol": "PI_XBTUSD", "type": "futures_inverse", "contractSize": 1, "contractValueTradePrecision": 0}]}
    assert futures_order_size("PI_XBTUSD", 310.31, 77_000, instruments) == 310.0


def test_validate_order_response_rejects_invalid_size_envelope():
    with pytest.raises(KrakenCliCommandFailed):
        validate_order_response({"result": "success", "status": "invalidSize", "order_id": "x"})
