from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.events import lifespan
from app.middleware.auth_middleware import AuthMiddleware
from app.middleware.cors_middleware import register_cors
from app.middleware.error_handler import register_exception_handlers
from app.middleware.logging_middleware import LoggingMiddleware
from app.routers import api_router


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description=(
            "APEX — AI Personal Assistant OS. "
            "A deeply loyal, emotionally intelligent personal assistant that watches, "
            "thinks, coordinates, and acts on your behalf."
        ),
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── Middleware (order matters: outermost = first to run) ──────────────────
    register_cors(app)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(AuthMiddleware)

    # ── Exception handlers ────────────────────────────────────────────────────
    register_exception_handlers(app)

    # ── Routers ───────────────────────────────────────────────────────────────
    from fastapi import Depends
    from fastapi.security import HTTPBearer
    security = HTTPBearer(auto_error=False)
    app.include_router(api_router, dependencies=[Depends(security)])

    # ── Health check (no auth) ────────────────────────────────────────────────
    @app.get("/health", tags=["Health"])
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "app": settings.app_name})

    @app.get("/", tags=["Health"])
    async def root() -> JSONResponse:
        return JSONResponse({"message": f"Welcome to {settings.app_name} API"})

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        workers=settings.app_workers,
        reload=settings.app_debug,
        log_config=None,  # structlog handles logging
    )
