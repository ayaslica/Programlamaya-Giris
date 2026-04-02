from __future__ import annotations

import pandas as pd

from app.core.config import Settings, get_settings


class DivergenceService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @staticmethod
    def _swings(series: pd.Series, lookback: int) -> tuple[list[int], list[int]]:
        highs, lows = [], []
        for i in range(lookback, len(series) - lookback):
            window = series.iloc[i - lookback : i + lookback + 1]
            center = series.iloc[i]
            if center >= window.max():
                highs.append(i)
            if center <= window.min():
                lows.append(i)
        return highs, lows

    def detect(self, df: pd.DataFrame, rsi_series: pd.Series) -> dict[str, float | bool]:
        lookback = self.settings.analysis.divergence_lookback
        min_dist = self.settings.analysis.divergence_min_distance

        price_highs, price_lows = self._swings(df["close"], lookback)
        rsi_highs, rsi_lows = self._swings(rsi_series.fillna(50), lookback)

        regular_bullish, hidden_bullish = False, False
        regular_bearish, hidden_bearish = False, False

        if len(price_lows) >= 2 and len(rsi_lows) >= 2:
            p1, p2 = price_lows[-2], price_lows[-1]
            r1, r2 = rsi_lows[-2], rsi_lows[-1]
            if abs(p2 - p1) >= min_dist and abs(r2 - r1) >= min_dist:
                regular_bullish = df["close"].iloc[p2] < df["close"].iloc[p1] and rsi_series.iloc[r2] > rsi_series.iloc[r1]
                hidden_bullish = df["close"].iloc[p2] > df["close"].iloc[p1] and rsi_series.iloc[r2] < rsi_series.iloc[r1]

        if len(price_highs) >= 2 and len(rsi_highs) >= 2:
            p1, p2 = price_highs[-2], price_highs[-1]
            r1, r2 = rsi_highs[-2], rsi_highs[-1]
            if abs(p2 - p1) >= min_dist and abs(r2 - r1) >= min_dist:
                regular_bearish = df["close"].iloc[p2] > df["close"].iloc[p1] and rsi_series.iloc[r2] < rsi_series.iloc[r1]
                hidden_bearish = df["close"].iloc[p2] < df["close"].iloc[p1] and rsi_series.iloc[r2] > rsi_series.iloc[r1]

        return {
            "regular_bullish": regular_bullish,
            "hidden_bullish": hidden_bullish,
            "regular_bearish": regular_bearish,
            "hidden_bearish": hidden_bearish,
            "score": (1 if regular_bullish else 0) + (0.7 if hidden_bullish else 0) - (1 if regular_bearish else 0) - (0.7 if hidden_bearish else 0),
        }
