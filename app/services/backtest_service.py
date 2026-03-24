from __future__ import annotations

from statistics import mean

import numpy as np

from app.core.config import Settings, get_settings
from app.models.schemas import BacktestMetrics, BacktestRequest, BacktestResponse, Trade
from app.services.analysis_service import AnalysisService
from app.services.cache_service import layer_backtest_cache


class BacktestService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.analysis = AnalysisService(self.settings)

    def run(self, req: BacktestRequest) -> BacktestResponse:
        cache_key = f"backtest:{req.model_dump_json()}"
        cached = layer_backtest_cache.get(cache_key)
        if cached:
            return cached

        df = self.analysis.data_service.get_ohlcv(req.symbol, req.timeframe, req.period)

        min_score = req.min_score
        stop_loss = req.stop_loss_pct or self.settings.risk.stop_loss_pct
        take_profit = req.take_profit_pct or self.settings.risk.take_profit_pct
        trailing = req.trailing_stop_pct or self.settings.risk.trailing_stop_pct
        time_stop = req.time_stop_bars or self.settings.risk.time_stop_bars
        fee_pct = req.fee_pct if req.fee_pct is not None else self.settings.risk.fee_pct
        slippage = req.slippage_pct if req.slippage_pct is not None else self.settings.risk.slippage_pct

        trades: list[Trade] = []
        equity = [1.0]
        buy_hold_curve = [1.0]
        drawdown_curve = [0.0]
        peak = 1.0

        in_position = False
        entry_price = 0.0
        entry_idx = 0
        trailing_stop = None

        for i in range(self.settings.analysis.min_bars, len(df)):
            price = float(df["close"].iloc[i])
            bh_return = price / float(df["close"].iloc[self.settings.analysis.min_bars])
            buy_hold_curve.append(bh_return)

            window_df = df.iloc[: i + 1]
            indicators = self.analysis.indicator_service.calculate(req.symbol, req.timeframe, req.period or "auto", window_df)
            divergence = self.analysis.divergence_service.detect(window_df, self.analysis._rsi_series(window_df))
            base_score = self.analysis._weighted_indicator_score(indicators) + divergence["score"]
            rule_score, _, mandatory_ok = self.analysis.rule_engine.evaluate(indicators)
            score = base_score + rule_score

            if not in_position and score >= min_score and mandatory_ok:
                in_position = True
                entry_price = price * (1 + slippage)
                entry_idx = i
                trailing_stop = entry_price * (1 - trailing)
                continue

            if in_position:
                holding_bars = i - entry_idx
                pnl = (price - entry_price) / entry_price
                trailing_stop = max(trailing_stop or 0, price * (1 - trailing))

                exit_reason = None
                if price <= entry_price * (1 - stop_loss):
                    exit_reason = "stop_loss"
                elif price >= entry_price * (1 + take_profit):
                    exit_reason = "take_profit"
                elif trailing_stop and price <= trailing_stop:
                    exit_reason = "trailing_stop"
                elif holding_bars >= time_stop:
                    exit_reason = "time_stop"
                elif score <= self.settings.thresholds["sell"]:
                    exit_reason = "reverse_signal"

                if exit_reason:
                    exit_price = price * (1 - slippage)
                    ret = ((exit_price - entry_price) / entry_price) - 2 * fee_pct
                    trades.append(
                        Trade(
                            entry_time=df.index[entry_idx].to_pydatetime(),
                            exit_time=df.index[i].to_pydatetime(),
                            entry_price=round(entry_price, 5),
                            exit_price=round(exit_price, 5),
                            return_pct=round(ret * 100, 4),
                            exit_reason=exit_reason,
                        )
                    )
                    equity.append(equity[-1] * (1 + ret))
                    peak = max(peak, equity[-1])
                    drawdown_curve.append((equity[-1] - peak) / peak * 100)
                    in_position = False

        returns = [t.return_pct / 100 for t in trades]
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r < 0]

        total_return = (equity[-1] - 1) * 100 if len(equity) > 1 else 0.0
        win_rate = (len(wins) / len(returns) * 100) if returns else 0.0
        profit_factor = (sum(wins) / abs(sum(losses))) if losses else float("inf") if wins else 0.0
        max_dd = min(drawdown_curve) if drawdown_curve else 0.0
        durations = [
            (t.exit_time - t.entry_time).total_seconds() / 3600 if req.timeframe == "1h" else (t.exit_time - t.entry_time).days
            for t in trades
        ]
        sharpe = (mean(returns) / (np.std(returns) + 1e-9)) * np.sqrt(252) if returns else 0.0

        metrics = BacktestMetrics(
            total_return_pct=round(total_return, 4),
            win_rate_pct=round(win_rate, 2),
            total_trades=len(trades),
            profit_factor=round(profit_factor, 3) if np.isfinite(profit_factor) else 999.0,
            max_drawdown_pct=round(max_dd, 4),
            avg_trade_duration_bars=round(mean(durations), 2) if durations else 0.0,
            sharpe_ratio=round(float(sharpe), 3),
        )

        strategy_comment = (
            "Strateji trend + momentum odaklıdır; düşük işlem sayısında parametreleri gevşetin."
            if len(trades) < 10
            else "Strateji dengeli işlem üretmiştir; risk/ödül oranı sürdürülebilir görünüyor."
        )

        response = BacktestResponse(
            symbol=req.symbol,
            timeframe=req.timeframe,
            metrics=metrics,
            equity_curve=[round(v, 6) for v in equity],
            drawdown_curve=[round(v, 6) for v in drawdown_curve],
            buy_hold_curve=[round(v, 6) for v in buy_hold_curve],
            trades=trades,
            strategy_comment=strategy_comment,
            warnings=[],
        )

        layer_backtest_cache.set(cache_key, response, self.settings.cache.backtest_ttl_sec)
        return response
