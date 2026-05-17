import pytest

from mirror.clients.kraken import KrakenClient, KrakenCommandResult, extract_xstock_perp_symbols, format_cli_number, is_xstock_perp_symbol, select_best_xstock_record
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
