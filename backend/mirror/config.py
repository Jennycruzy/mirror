from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://mirror:mirror@localhost:5432/mirror"
    kraken_cli_path: str = "kraken"
    kraken_api_key: str | None = None
    kraken_api_secret: str | None = None
    kraken_futures_url: str | None = None
    kraken_danger_allow_any_url_host: bool = False
    kraken_execution_mode: str = "paper"
    kraken_require_paper_mode: bool = True
    trading_pair: str = "BTC/USD"
    trading_pairs: str = "BTC/USD,ETH/USD,SOL/USD"
    trading_futures_symbols: str = "PI_XBTUSD,PI_ETHUSD,PI_XRPUSD"
    featherless_api_key: str | None = None
    featherless_base_url: str = "https://api.featherless.ai/v1"
    featherless_model: str = "Qwen/Qwen2.5-7B-Instruct"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3-pro"
    patcher_provider: str = "featherless"
    patcher_base_url: str | None = None
    patcher_api_key: str | None = None
    patcher_model: str | None = None
    base_sepolia_rpc_url: str = "https://sepolia.base.org"
    base_sepolia_chain_id: int = 84532
    owner_private_key: str | None = None
    evaluator_private_key: str | None = None
    erc8004_identity_registry: str = "0x8004A818BFB912233c491871b3d84c89A494BD9e"
    erc8004_reputation_registry: str = "0x8004B663056A597Dffe9eCcC1965A193B7388713"
    pinata_jwt: str | None = None
    web3_storage_token: str | None = None
    public_app_url: str = "http://localhost:3000"
    backend_public_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:3000,http://localhost:3010"
    trading_enabled: bool = False
    onchain_enabled: bool = False
    mirror_mode: str = "calibration"
    tournament_objective: str = "pnl"
    tournament_max_daily_drawdown_pct: float = Field(default=15.0, gt=0, le=100)
    tournament_max_position_risk_pct: float = Field(default=3.0, gt=0, le=100)
    tournament_min_confidence: float = Field(default=0.55, ge=0, le=1)
    tournament_account_equity_usd: float = Field(default=10_000.0, gt=0)
    tournament_min_expected_move_bps: float = Field(default=20.0, ge=0, le=500)
    tournament_max_concurrent_positions: int = Field(default=3, ge=1)
    tournament_scout_equity_pct: float = Field(default=4.0, gt=0, le=100)
    tournament_aggressive_equity_pct: float = Field(default=12.0, gt=0, le=100)
    tournament_max_symbol_exposure_pct: float = Field(default=25.0, gt=0, le=100)
    tournament_min_quote_volume: float = Field(default=0.0, ge=0)
    tournament_symbol_spread_caps: str = "PI_XBTUSD:10,PI_ETHUSD:12,PI_XRPUSD:25,PI_LTCUSD:25,PI_BCHUSD:35,PF_SOLUSD:250"
    tournament_exit_check_seconds: int = Field(default=20, ge=5)
    tournament_min_pnl_improvement_pct: float = Field(default=10.0, ge=0)
    tournament_max_drawdown_worsening_pct: float = Field(default=20.0, ge=0)
    tournament_max_brier_degradation_pct: float = Field(default=10.0, ge=0)
    blue_min_sample_size: int = Field(default=8, ge=1)
    blue_pending_sample_size: int = Field(default=12, ge=1)
    blue_pending_brier_gap: float = Field(default=0.06, ge=0, le=1)
    kraken_timeout_seconds: float = Field(default=30.0, gt=0)

    def trading_pairs_list(self) -> list[str]:
        pairs = [pair.strip() for pair in self.trading_pairs.split(",") if pair.strip()]
        if pairs:
            return pairs
        return [self.trading_pair]

    def trading_futures_symbols_list(self) -> list[str]:
        symbols = [symbol.strip() for symbol in self.trading_futures_symbols.split(",") if symbol.strip()]
        return symbols

    def tournament_symbol_spread_caps_map(self) -> dict[str, float]:
        caps: dict[str, float] = {}
        for item in self.tournament_symbol_spread_caps.split(","):
            if ":" not in item:
                continue
            symbol, raw_cap = item.split(":", 1)
            symbol = symbol.strip().upper()
            try:
                caps[symbol] = float(raw_cap.strip())
            except ValueError:
                continue
        return caps


@lru_cache
def get_settings() -> Settings:
    return Settings()
