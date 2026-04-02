from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.v1.routes import router, ui_router
from app.utils.logging_setup import configure_logging
from app.utils.middleware import RateLimitMiddleware, RequestContextMiddleware

configure_logging()

app = FastAPI(
    title="FinAnalytica API",
    description="Modüler finansal analiz, sinyal, tarama ve backtest sistemi",
    version="1.0.0",
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(RateLimitMiddleware)
app.include_router(router)
app.include_router(ui_router)
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
