from __future__ import annotations

from datetime import datetime, timedelta, timezone
from difflib import get_close_matches

import numpy as np
import pandas as pd

from app.core.config import Settings, get_settings
from app.services.cache_service import layer_ohlcv_cache

SYMBOL_HINTS = ["THYAO.IS", "BTC.USDT", "AAPL.USD", "ETH.USDT", "XU100.TRY"]


class DataNotFoundError(Exception):
    pass


class DataService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @staticmethod
    def _market_is_open(now: datetime | None = None) -> bool:
        now = now or datetime.now(tz=timezone.utc)
        is_weekday = now.weekday() < 5
        return is_weekday and 13 <= now.hour <= 20

    def _suggest_symbol(self, symbol: str) -> str:
        matches = get_close_matches(symbol.upper(), SYMBOL_HINTS, n=1, cutoff=0.45)
        return matches[0] if matches else f"{symbol}.IS"

    def _generate_mock_ohlcv(self, bars: int = 400) -> pd.DataFrame:
        idx = pd.date_range(datetime.now(tz=timezone.utc) - timedelta(days=bars), periods=bars, freq="D")
        base = np.cumsum(np.random.normal(0.3, 1.2, size=bars)) + 100
        close = np.maximum(base, 1)
        open_ = close + np.random.normal(0, 0.8, size=bars)
        high = np.maximum(open_, close) + np.random.uniform(0.2, 1.5, size=bars)
        low = np.minimum(open_, close) - np.random.uniform(0.2, 1.5, size=bars)
        volume = np.random.uniform(1000, 10000, size=bars)
        return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=idx)

    def get_ohlcv(self, symbol: str, timeframe: str, period: str | None = None) -> pd.DataFrame:
        period = period or self.settings.analysis.default_period_map.get(timeframe, "6mo")
        cache_key = f"ohlcv:{symbol}:{timeframe}:{period}"
        cached = layer_ohlcv_cache.get(cache_key)
        if cached is not None:
            return cached.copy()

        data = None
        warning: list[str] = []

        try:
            import yfinance as yf  # type: ignore

            ticker_symbol = symbol.split(".")[0] if symbol.endswith(".USDT") else symbol
            yf_symbol = f"{ticker_symbol}-USD" if symbol.endswith(".USDT") else ticker_symbol
            interval = timeframe
            if timeframe == "4h":
                interval = "1h"
            raw = yf.download(yf_symbol, period=period, interval=interval, progress=False, auto_adjust=False)
            if not raw.empty:
                raw.columns = [str(col).lower() for col in raw.columns]
                data = raw[["open", "high", "low", "close", "volume"]].dropna()
                if timeframe == "4h":
                    data = data.resample("4H").agg(
                        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
                    ).dropna()
        except Exception:
            warning.append("Canlı veri alınamadı, mock veri kullanıldı.")

        if data is None or data.empty:
            if symbol.endswith(".MOCK"):
                data = self._generate_mock_ohlcv()
            else:
                suggestion = self._suggest_symbol(symbol)
                raise DataNotFoundError(f"{symbol} için veri bulunamadı. {suggestion} deneyin.")

        ttl = self.settings.cache.ohlcv_open_ttl_sec if self._market_is_open() else self.settings.cache.ohlcv_closed_ttl_sec
        layer_ohlcv_cache.set(cache_key, data, ttl)
        data.attrs["warnings"] = warning
        return data.copy()
