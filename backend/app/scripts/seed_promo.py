"""Seed promo codes (SQLite-safe)."""
import asyncio
from datetime import datetime, timedelta
from app.database import AsyncSessionLocal
from app.models.p2e import PromoCode
from sqlalchemy import select


async def main():
    async with AsyncSessionLocal() as db:
        codes = [
            {"code": "WELCOME100", "reward": 100, "max_uses": None, "expires_at": None},
            {"code": "MINER500", "reward": 500, "max_uses": 1000, "expires_at": None},
            {"code": "GOLD1000", "reward": 1000, "max_uses": None,
             "expires_at": datetime.now() + timedelta(days=30)},
        ]
        for c in codes:
            exists = (await db.execute(
                select(PromoCode).where(PromoCode.code == c["code"])
            )).scalar_one_or_none()
            if not exists:
                db.add(PromoCode(**c))
                print(f"added {c['code']}")
            else:
                print(f"exists {c['code']}")
        await db.commit()
        print("promo codes seeded")


if __name__ == "__main__":
    asyncio.run(main())
