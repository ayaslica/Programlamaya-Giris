from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

from app.core.config import Settings, get_settings
from app.models.schemas import ScanRequest
from app.services.analysis_service import AnalysisService
from app.services.cache_service import layer_scan_cache


class ScanService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.analysis_service = AnalysisService(self.settings)

    def run_scan(self, req: ScanRequest) -> dict:
        symbols = req.symbols[: self.settings.scan.max_symbols]
        cache_key = f"scan:{req.model_dump_json()}"
        cached = layer_scan_cache.get(cache_key)
        if cached:
            return cached

        signals = []
        with ThreadPoolExecutor(max_workers=self.settings.scan.max_workers) as executor:
            futures = {
                executor.submit(self.analysis_service.analyze, sym, req.timeframe, req.period, False): sym for sym in symbols
            }
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    signals.append(future.result().model_dump())
                except Exception as exc:
                    signals.append({"symbol": symbol, "error": str(exc)})

        ok_signals = [s for s in signals if "score" in s]
        returns = [s["score"] / 10 for s in ok_signals]

        payload = {
            "mode": req.mode,
            "timeframe": req.timeframe,
            "results": signals,
            "metrics": {
                "win_rate": round(sum(1 for r in returns if r > 0) / len(returns) * 100, 2) if returns else 0,
                "average_return": round(float(np.mean(returns) * 100), 3) if returns else 0,
                "max_drawdown": round(float(min(returns) * 100), 3) if returns else 0,
                "sharpe_ratio": round(float(np.mean(returns) / (np.std(returns) + 1e-9) * np.sqrt(252)), 3)
                if returns
                else 0,
            },
            "portfolio": None,
        }

        if req.mode == "portfolio" and ok_signals:
            equal_weight = 1 / len(ok_signals)
            portfolio_score = sum(s["score"] * equal_weight for s in ok_signals)
            payload["portfolio"] = {
                "method": "equal_weight_daily_rebalance",
                "basket_score": round(portfolio_score, 3),
                "weights": {s["symbol"]: round(equal_weight, 4) for s in ok_signals},
            }

        layer_scan_cache.set(cache_key, payload, self.settings.cache.scan_results_ttl_sec)
        return payload
