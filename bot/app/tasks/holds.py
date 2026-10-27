import asyncio

from app.core.db import engine, session_factory
from app.services.booking import release_expired_holds
from app.tasks.celery_app import celery_app


async def _release() -> int:
    try:
        async with session_factory() as session, session.begin():
            released = await release_expired_holds(session)
            return len(released)
    finally:
        await engine.dispose()


@celery_app.task(  # type: ignore[untyped-decorator]
    name="booking.release_expired_holds",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=5,
)
def release_expired_holds_task() -> int:
    return asyncio.run(_release())
