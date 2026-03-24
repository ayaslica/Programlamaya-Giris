from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import get_settings


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-ms"] = f"{duration_ms:.2f}"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.settings = get_settings()
        self.bucket: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = 60
        max_req = self.settings.rate_limit.requests_per_minute

        queue = self.bucket[ip]
        while queue and queue[0] < now - window:
            queue.popleft()

        if len(queue) >= max_req:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded: 60 request/min/IP"})

        queue.append(now)
        return await call_next(request)
