from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://mirror:mirror@localhost:5432/mirror"
    kraken_cli_path: str = "kraken"
    kraken_require_paper_mode: bool = True
    featherless_api_key: str | None = None
    featherless_base_url: str = "https://api.featherless.ai/v1"
    featherless_model: str = "Qwen/Qwen2.5-7B-Instruct"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3-pro"
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
    trading_enabled: bool = False
    onchain_enabled: bool = False
    kraken_timeout_seconds: float = Field(default=30.0, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()

