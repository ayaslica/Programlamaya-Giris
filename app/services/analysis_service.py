from __future__ import annotations

import pandas as pd

from app.core.config import Settings, get_settings
from app.models.schemas import SignalResponse
from app.services.data_service import DataNotFoundError, DataService
from app.services.divergence_service import DivergenceService
from app.services.indicator_service import IndicatorService
from app.services.rule_engine import RuleEngine


class AnalysisService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.data_service = DataService(self.settings)
        self.indicator_service = IndicatorService(self.settings)
        self.divergence_service = DivergenceService(self.settings)
        self.rule_engine = RuleEngine(self.settings)

    def analyze(self, symbol: str, timeframe: str, period: str | None, debug: bool = False) -> SignalResponse:
        if timeframe not in self.settings.analysis.timeframes:
            raise ValueError(f"Timeframe desteklenmiyor: {timeframe}")

        df = self.data_service.get_ohlcv(symbol, timeframe, period)
        warnings = list(df.attrs.get("warnings", []))
        if len(df) < self.settings.analysis.min_bars:
            warnings.append(
                f"Yetersiz veri: {len(df)} bar mevcut. Minimum {self.settings.analysis.min_bars} bar önerilir."
            )

        indicators = self.indicator_service.calculate(symbol, timeframe, period or "auto", df)

        rsi_series = self._rsi_series(df)
        divergence = self.divergence_service.detect(df, rsi_series)

        factor_score = self._weighted_indicator_score(indicators)
        div_score = divergence["score"]

        rule_score, debug_info, mandatory_ok = self.rule_engine.evaluate(indicators)
        score = factor_score + div_score + rule_score

        signal = "WAIT"
        if score >= self.settings.thresholds["buy"] and mandatory_ok:
            signal = "BUY"
        elif score <= self.settings.thresholds["sell"]:
            signal = "SELL"

        return SignalResponse(
            symbol=symbol,
            timeframe=timeframe,
            score=round(score, 3),
            signal=signal,
            indicators={k: round(v, 4) for k, v in indicators.items()},
            divergence=divergence,
            debug=debug_info if debug else [],
            warnings=warnings,
        )

    @staticmethod
    def _rsi_series(df: pd.DataFrame) -> pd.Series:
        delta = df["close"].diff().fillna(0)
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, pd.NA)
        return 100 - (100 / (1 + rs))

    def _weighted_indicator_score(self, indicators: dict[str, float]) -> float:
        w = self.settings.weights
        score = 0.0
        score += w.get("rsi", 0) * (1 if indicators["rsi"] < 35 else -1 if indicators["rsi"] > 70 else 0)
        score += w.get("macd", 0) * (1 if indicators["macd_hist"] > 0 else -1)
        score += w.get("vwap", 0) * (1 if indicators["close"] > indicators["vwap"] else -1)
        score += w.get("cvd", 0) * (1 if indicators["cvd"] > 0 else -1)
        score += w.get("ema_sma", 0) * (1 if indicators["ema_fast"] > indicators["ema_slow"] else -1)
        score += w.get("ichimoku", 0) * (1 if indicators["ichimoku_tenkan"] > indicators["ichimoku_kijun"] else -1)
        score += w.get("fibonacci", 0) * (1 if indicators["fib_zone"] < 0.382 else -1 if indicators["fib_zone"] > 0.786 else 0)
        score += w.get("mfi", 0) * (1 if 40 <= indicators["mfi"] <= 75 else -1)
        score += w.get("volume_profile", 0) * (1 if indicators["close"] > indicators["volume_profile_poc"] else -1)
        return score
