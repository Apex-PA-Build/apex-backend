from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.logging import get_logger

logger = get_logger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def start_scheduler() -> None:
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone="UTC")

    _scheduler.add_job(
        _check_and_fire_reminders,
        trigger="interval",
        minutes=5,
        id="reminder_checker",
        replace_existing=True,
    )

    _scheduler.add_job(
        _reset_daily_moods,
        trigger="cron",
        hour=0,
        minute=1,
        id="reset_moods",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("scheduler_started")


async def stop_scheduler() -> None:
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    logger.info("scheduler_stopped")


async def _check_and_fire_reminders() -> None:
    """Fire any due reminders and push them to connected users."""
    from app.core.supabase import get_client
    from app.services.notification import notification_manager
    from app.utils.datetime import utcnow

    try:
        client = await get_client()
        now = utcnow().isoformat()
        result = await (
            client.table("reminders")
            .select("*")
            .eq("status", "pending")
            .lte("remind_at", now)
            .execute()
        )
        reminders = result.data or []

        for reminder in reminders:
            await notification_manager.send(reminder["user_id"], {
                "event": "reminder_fired",
                "reminder": reminder,
            })
            await client.table("reminders").update({"status": "fired"}).eq("id", reminder["id"]).execute()

        if reminders:
            logger.info("reminders_fired", count=len(reminders))
    except Exception as e:
        logger.error("reminder_check_failed", error=str(e))


async def _reset_daily_moods() -> None:
    """Clear mood_today at midnight so each day starts fresh."""
    try:
        from app.core.supabase import get_client
        client = await get_client()
        await client.table("profiles").update({"mood_today": None}).neq("mood_today", None).execute()
        logger.info("moods_reset")
    except Exception as e:
        logger.error("mood_reset_failed", error=str(e))
