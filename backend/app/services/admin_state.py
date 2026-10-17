"""Admin state — GarageInc pattern: admin access is an allowlist of Telegram
IDs (their template reads ADMIN_* IDs from env; /admin silently ignores
everyone else). Here the allowlist comes from SPACEHUNTER_ADMIN_IDS
(comma-separated), defaulting to the demo user so the panel works out of the
box in the demo. Toggles live in the admin_settings table."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except Exception:
    pass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.features import AdminSetting

_DEFAULT_ADMINS = "99281932"


def admin_ids() -> set[int]:
    raw = os.environ.get("SPACEHUNTER_ADMIN_IDS", _DEFAULT_ADMINS)
    out = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out


def is_admin(telegram_id: int) -> bool:
    return int(telegram_id) in admin_ids()


async def get_setting(db: AsyncSession, key: str, default: str = "") -> str:
    row = await db.get(AdminSetting, key)
    return row.value if row is not None else default


async def set_setting(db: AsyncSession, key: str, value: str) -> None:
    row = await db.get(AdminSetting, key)
    if row is None:
        db.add(AdminSetting(key=key, value=value))
    else:
        row.value = value


async def referrals_enabled(db: AsyncSession) -> bool:
    return (await get_setting(db, "referrals_enabled", "1")) != "0"


async def arcade_enabled(db: AsyncSession) -> bool:
    return (await get_setting(db, "arcade_enabled", "1")) != "0"


async def announcement(db: AsyncSession) -> str:
    return await get_setting(db, "announcement", "")
