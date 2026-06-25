import time
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.websockets import WebSocketState
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

# Prometheus Metrics Definition
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests processed",
    ["method", "endpoint", "status"]
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0)
)

WEBSOCKET_CONNECTIONS_ACTIVE = Gauge(
    "websocket_connections_active",
    "Number of active WebSocket connections",
    ["endpoint"]
)

DATABASE_QUERY_DURATION_SECONDS = Histogram(
    "database_query_duration_seconds",
    "PostgreSQL query execution latencies in seconds",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5)
)

REDIS_LATENCY_SECONDS = Histogram(
    "redis_latency_seconds",
    "Redis operation latency in seconds",
    buckets=(0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25)
)

class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Avoid scraping metrics endpoint or static files recursively
        path = request.url.path
        if path == "/metrics" or path == "/health":
            return await call_next(request)
            
        method = request.method
        start_time = time.perf_counter()
        
        try:
            response = await call_next(request)
            duration = time.perf_counter() - start_time
            
            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                endpoint=path,
                status=response.status_code
            ).inc()
            
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method,
                endpoint=path
            ).observe(duration)
            
            return response
        except Exception as e:
            duration = time.perf_counter() - start_time
            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                endpoint=path,
                status=500
            ).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method,
                endpoint=path
            ).observe(duration)
            raise e

def register_metrics_route(app):
    # Endpoint to serve Prometheus scraping data
    @app.get("/metrics")
    def metrics():
        # Dynamically sample database and redis latency for telemetry
        # In a real environment, we would monitor pools. For mock observability:
        from app.db.redis import redis_client
        from app.db.session import AsyncSessionLocal
        from sqlalchemy import text
        import asyncio
        
        async def check_db_latency():
            t0 = time.perf_counter()
            try:
                async with AsyncSessionLocal() as session:
                    await session.execute(text("SELECT 1"))
                DATABASE_QUERY_DURATION_SECONDS.observe(time.perf_counter() - t0)
            except Exception:
                pass

        async def check_redis_latency():
            t0 = time.perf_counter()
            try:
                await redis_client.ping()
                REDIS_LATENCY_SECONDS.observe(time.perf_counter() - t0)
            except Exception:
                pass
                
        # Run pings in background (non-blocking for response)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(check_db_latency())
            loop.create_task(check_redis_latency())
        except RuntimeError:
            pass

        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )
