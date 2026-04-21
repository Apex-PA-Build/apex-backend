from supabase import acreate_client, AsyncClient

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_client: AsyncClient | None = None


async def get_client() -> AsyncClient:
    global _client
    if _client is None:
        _client = await acreate_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
        logger.info("supabase_connected", url=settings.supabase_url)
    return _client


async def close_client() -> None:
    global _client
    _client = None
    logger.info("supabase_disconnected")
