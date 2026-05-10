from fastapi import APIRouter

from app.api.v1 import (
    activities,
    admin,
    auth,
    chat,
    children,
    chors,
    debug,
    events,
    expenses,
    families,
    push,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(families.router)
api_router.include_router(users.router)
api_router.include_router(children.router)
api_router.include_router(events.router)
api_router.include_router(chors.router)
api_router.include_router(activities.router)
api_router.include_router(expenses.router)
api_router.include_router(chat.router)
api_router.include_router(push.router)
api_router.include_router(admin.router)
api_router.include_router(debug.router)
