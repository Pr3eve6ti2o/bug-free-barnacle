import asyncio
from app.database import engine, Base
from app.models.features import ArcadeResult, ButtonState, ButtonUser, DropClaim  # noqa

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("feature tables created")

asyncio.run(main())
