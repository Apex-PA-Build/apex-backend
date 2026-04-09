from fastapi import APIRouter

from app.routers import (
    agent,
    auth,
    brief,
    calendar,
    calls,
    chat,
    goals,
    integrations,
    memory,
    reminders,
    tasks,
    websockets,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router,         prefix="/auth",         tags=["Auth"])
api_router.include_router(brief.router,        prefix="/brief",        tags=["Brief"])
api_router.include_router(tasks.router,        prefix="/tasks",        tags=["Tasks"])
api_router.include_router(goals.router,        prefix="/goals",        tags=["Goals"])
api_router.include_router(calendar.router,     prefix="/calendar",     tags=["Calendar"])
api_router.include_router(memory.router,       prefix="/memory",       tags=["Memory"])
api_router.include_router(agent.router,        prefix="/agent",        tags=["Agent"])
api_router.include_router(integrations.router, prefix="/integrations", tags=["Integrations"])
api_router.include_router(calls.router,        prefix="/calls",        tags=["Calls"])
api_router.include_router(reminders.router,    prefix="/reminders",    tags=["Reminders"])
api_router.include_router(chat.router,         prefix="/chat",         tags=["Chat"])
api_router.include_router(websockets.router,   prefix="/ws",           tags=["WebSockets"])
