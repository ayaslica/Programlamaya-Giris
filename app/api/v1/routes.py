from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.models.schemas import AnalyzeRequest, BacktestRequest, ScanRequest
from app.services.analysis_service import AnalysisService
from app.services.backtest_service import BacktestService
from app.services.data_service import DataNotFoundError
from app.services.scan_service import ScanService

router = APIRouter(prefix="/api/v1", tags=["v1"])
analysis_service = AnalysisService()
scan_service = ScanService()
backtest_service = BacktestService()


@router.post("/analyze")
def analyze(req: AnalyzeRequest):
    try:
        return analysis_service.analyze(req.symbol, req.timeframe, req.period, req.debug)
    except DataNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scan")
def scan(req: ScanRequest):
    return scan_service.run_scan(req)


@router.post("/backtest")
def backtest(req: BacktestRequest):
    try:
        return backtest_service.run(req)
    except DataNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/period-options/{timeframe}")
def period_options(timeframe: str):
    options = {
        "1h": ["7d", "30d", "60d", "90d"],
        "4h": ["30d", "90d", "180d", "365d"],
        "1d": ["6mo", "1y", "3y", "5y"],
    }
    if timeframe not in options:
        raise HTTPException(status_code=400, detail="Invalid timeframe")
    return {"timeframe": timeframe, "periods": options[timeframe]}


ui_router = APIRouter(tags=["ui"])


@ui_router.get("/")
def home():
    return FileResponse("frontend/index.html")
