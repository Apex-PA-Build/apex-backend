from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.exceptions import APEXError
from app.core.logging import get_logger

logger = get_logger(__name__)


async def apex_exception_handler(request: Request, exc: APEXError) -> JSONResponse:
    if exc.status_code >= 500:
        logger.error("apex_error", status=exc.status_code, detail=exc.detail, path=request.url.path)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_error", path=request.url.path, error=str(exc))
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred"})
