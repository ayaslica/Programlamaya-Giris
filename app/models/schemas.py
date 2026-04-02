from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


Timeframe = Literal["1h", "4h", "1d"]


class AnalyzeRequest(BaseModel):
    symbol: str = Field(..., description="SYMBOL.BASE formatında sembol")
    timeframe: Timeframe = "1d"
    period: str | None = None
    debug: bool = False


class ScanRequest(BaseModel):
    symbols: list[str]
    timeframe: Timeframe = "1d"
    period: str | None = None
    mode: Literal["independent", "portfolio"] = "independent"


class BacktestRequest(BaseModel):
    symbol: str
    timeframe: Timeframe = "1d"
    period: str | None = None
    min_score: float = 4.0
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    trailing_stop_pct: float | None = None
    time_stop_bars: int | None = None
    fee_pct: float | None = None
    slippage_pct: float | None = None
    risk_mode: Literal["percent", "fixed"] = "percent"


class RuleDebug(BaseModel):
    name: str
    passed: bool
    score_contribution: float
    reason: str
    rule_type: str


class SignalResponse(BaseModel):
    symbol: str
    timeframe: Timeframe
    score: float
    signal: Literal["BUY", "SELL", "WAIT"]
    indicators: dict[str, float]
    divergence: dict[str, float | bool]
    debug: list[RuleDebug] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Trade(BaseModel):
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    return_pct: float
    exit_reason: str


class BacktestMetrics(BaseModel):
    total_return_pct: float
    win_rate_pct: float
    total_trades: int
    profit_factor: float
    max_drawdown_pct: float
    avg_trade_duration_bars: float
    sharpe_ratio: float


class BacktestResponse(BaseModel):
    symbol: str
    timeframe: Timeframe
    metrics: BacktestMetrics
    equity_curve: list[float]
    drawdown_curve: list[float]
    buy_hold_curve: list[float]
    trades: list[Trade]
    strategy_comment: str
    warnings: list[str] = Field(default_factory=list)
