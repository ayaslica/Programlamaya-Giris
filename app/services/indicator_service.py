from __future__ import annotations

import numpy as np
import pandas as pd

from app.core.config import Settings, get_settings
from app.services.cache_service import layer_indicator_cache


class IndicatorService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def calculate(self, symbol: str, timeframe: str, period: str, df: pd.DataFrame) -> dict[str, float]:
        key = f"indicators:{symbol}:{timeframe}:{period}:{len(df)}"
        cached = layer_indicator_cache.get(key)
        if cached:
            return dict(cached)

        close, high, low, volume = df["close"], df["high"], df["low"], df["volume"]
        fallbacks = self.settings.fallbacks

        ema_fast = close.ewm(span=12).mean().iloc[-1] if len(close) >= 12 else fallbacks["ema"]
        ema_slow = close.ewm(span=26).mean().iloc[-1] if len(close) >= 26 else fallbacks["ema"]
        sma_20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else fallbacks["sma"]

        delta = close.diff().fillna(0)
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss.replace(0, np.nan))
        rsi = (100 - (100 / (1 + rs))).iloc[-1] if not rs.empty else fallbacks["rsi"]

        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd = (ema12 - ema26).iloc[-1] if len(close) >= 26 else fallbacks["macd"]
        macd_signal_series = (ema12 - ema26).ewm(span=9).mean()
        macd_signal = macd_signal_series.iloc[-1] if len(close) >= 35 else fallbacks["macd_signal"]
        macd_hist = macd - macd_signal

        typical = (high + low + close) / 3
        vwap = (typical * volume).cumsum().iloc[-1] / volume.cumsum().iloc[-1] if volume.sum() > 0 else fallbacks["vwap"]

        signed_vol = np.where(delta >= 0, volume, -volume)
        cvd = pd.Series(signed_vol, index=df.index).cumsum().iloc[-1] if len(df) > 0 else fallbacks["cvd"]

        tenkan = ((high.rolling(9).max() + low.rolling(9).min()) / 2).iloc[-1] if len(df) >= 9 else fallbacks["ichimoku_tenkan"]
        kijun = ((high.rolling(26).max() + low.rolling(26).min()) / 2).iloc[-1] if len(df) >= 26 else fallbacks["ichimoku_kijun"]

        lowest14, highest14 = low.rolling(14).min(), high.rolling(14).max()
        money_flow = typical * volume
        positive_flow = pd.Series(np.where(typical.diff().fillna(0) > 0, money_flow, 0)).rolling(14).sum()
        negative_flow = pd.Series(np.where(typical.diff().fillna(0) < 0, money_flow, 0)).rolling(14).sum()
        mfi_ratio = positive_flow / negative_flow.replace(0, np.nan)
        mfi = (100 - (100 / (1 + mfi_ratio))).iloc[-1] if len(df) >= 14 else fallbacks["mfi"]

        lookback = min(120, len(df))
        l_low, l_high, current = low.tail(lookback).min(), high.tail(lookback).max(), close.iloc[-1]
        fib_zone = (current - l_low) / (l_high - l_low) if l_high != l_low else fallbacks["fib_zone"]

        bins = np.linspace(low.tail(lookback).min(), high.tail(lookback).max(), 20)
        hist, edges = np.histogram(close.tail(lookback), bins=bins, weights=volume.tail(lookback))
        poc_idx = int(np.argmax(hist)) if len(hist) > 0 else 0
        volume_profile_poc = float((edges[poc_idx] + edges[poc_idx + 1]) / 2) if len(edges) > 1 else fallbacks["volume_profile_poc"]

        indicators = {
            "close": float(current),
            "rsi": float(np.nan_to_num(rsi, nan=fallbacks["rsi"])),
            "macd": float(np.nan_to_num(macd, nan=fallbacks["macd"])),
            "macd_signal": float(np.nan_to_num(macd_signal, nan=fallbacks["macd_signal"])),
            "macd_hist": float(np.nan_to_num(macd_hist, nan=fallbacks["macd_hist"])),
            "vwap": float(np.nan_to_num(vwap, nan=fallbacks["vwap"])),
            "cvd": float(np.nan_to_num(cvd, nan=fallbacks["cvd"])),
            "ema_fast": float(np.nan_to_num(ema_fast, nan=fallbacks["ema"])),
            "ema_slow": float(np.nan_to_num(ema_slow, nan=fallbacks["ema"])),
            "sma_20": float(np.nan_to_num(sma_20, nan=fallbacks["sma"])),
            "ichimoku_tenkan": float(np.nan_to_num(tenkan, nan=fallbacks["ichimoku_tenkan"])),
            "ichimoku_kijun": float(np.nan_to_num(kijun, nan=fallbacks["ichimoku_kijun"])),
            "mfi": float(np.nan_to_num(mfi, nan=fallbacks["mfi"])),
            "fib_zone": float(np.nan_to_num(fib_zone, nan=fallbacks["fib_zone"])),
            "volume_profile_poc": float(np.nan_to_num(volume_profile_poc, nan=fallbacks["volume_profile_poc"])),
        }
        layer_indicator_cache.set(key, indicators, self.settings.cache.indicators_ttl_sec)
        return indicators
