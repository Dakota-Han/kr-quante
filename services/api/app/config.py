from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "local"
    kiwoom_mode: str = "mock"
    kiwoom_base_url: str = "https://mockapi.kiwoom.com"
    kiwoom_app_key: str = ""
    kiwoom_secret_key: str = ""
    kiwoom_account_no: str = ""
    allow_live_trading: bool = False
    require_manual_approval: bool = True
    disallow_market_orders: bool = True
    risk_per_trade: float = 0.003


settings = Settings()
