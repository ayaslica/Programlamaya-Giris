from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class AppSettings(BaseModel):
    name: str = "FinAnalytica"
    env: str = "dev"
    debug: bool = True
    default_timezone: str = "UTC"


class AnalysisSettings(BaseModel):
    min_bars: int = 100
    divergence_lookback: int = 5
    divergence_min_distance: int = 3
    default_period_map: dict[str, str] = Field(default_factory=lambda: {"1h": "60d", "4h": "180d", "1d": "3y"})
    timeframes: list[str] = Field(default_factory=lambda: ["1h", "4h", "1d"])


class RiskSettings(BaseModel):
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.04
    trailing_stop_pct: float = 0.015
    time_stop_bars: int = 24
    risk_per_trade_pct: float = 0.01
    fixed_lot: float = 1.0
    fee_pct: float = 0.001
    slippage_pct: float = 0.0005


class CacheSettings(BaseModel):
    ohlcv_open_ttl_sec: int = 300
    ohlcv_closed_ttl_sec: int = 3600
    indicators_ttl_sec: int = 1200
    backtest_ttl_sec: int = 86400
    scan_results_ttl_sec: int = 300


class ScanSettings(BaseModel):
    max_symbols: int = 20
    max_workers: int = 8
    rebalance_frequency: str = "daily"


class RateLimitSettings(BaseModel):
    requests_per_minute: int = 60


class Settings(BaseModel):
    app: AppSettings = Field(default_factory=AppSettings)
    thresholds: dict[str, float] = Field(default_factory=lambda: {"buy": 4.0, "sell": -3.0})
    weights: dict[str, float] = Field(default_factory=dict)
    fallbacks: dict[str, float] = Field(default_factory=dict)
    analysis: AnalysisSettings = Field(default_factory=AnalysisSettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    scan: ScanSettings = Field(default_factory=ScanSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    rules: dict[str, str] = Field(default_factory=lambda: {"path": "config/rules.json"})


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    config_path = Path(os.getenv("APP_CONFIG_PATH", "config/config.yaml"))
    payload: dict[str, Any] = {}
    if config_path.exists():
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    settings = Settings(**payload)

    if env_name := os.getenv("APP_ENV"):
        settings.app.env = env_name
    if debug_override := os.getenv("APP_DEBUG"):
        settings.app.debug = debug_override.lower() in {"1", "true", "yes"}
    if buy_threshold := os.getenv("BUY_THRESHOLD"):
        settings.thresholds["buy"] = float(buy_threshold)
    if sell_threshold := os.getenv("SELL_THRESHOLD"):
        settings.thresholds["sell"] = float(sell_threshold)

    return settings
