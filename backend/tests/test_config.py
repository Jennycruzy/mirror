from mirror.config import Settings


def test_trading_pairs_list_prefers_csv_basket():
    settings = Settings(trading_pair="BTC/USD", trading_pairs="BTC/USD, ETH/USD ,SOL/USD")
    assert settings.trading_pairs_list() == ["BTC/USD", "ETH/USD", "SOL/USD"]


def test_trading_pairs_list_falls_back_to_single_pair():
    settings = Settings(trading_pair="BTC/USD", trading_pairs=" ")
    assert settings.trading_pairs_list() == ["BTC/USD"]


def test_trading_futures_symbols_list_parses_csv():
    settings = Settings(trading_futures_symbols="PF_XBTUSD, PF_ETHUSD ,PF_SOLUSD")
    assert settings.trading_futures_symbols_list() == ["PF_XBTUSD", "PF_ETHUSD", "PF_SOLUSD"]


def test_tournament_symbol_spread_caps_map_parses_valid_items():
    settings = Settings(tournament_symbol_spread_caps="PI_XBTUSD:10, bad, PI_ETHUSD:12.5, PI_SOLUSD:nope")
    assert settings.tournament_symbol_spread_caps_map() == {"PI_XBTUSD": 10.0, "PI_ETHUSD": 12.5}
