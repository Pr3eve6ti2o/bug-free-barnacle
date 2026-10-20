"""Admin panel backend — modelled on GarageInc's bot Admin Panel:
an allowlist-gated menu of operator tools (Query User, Enable Referrals,
Send Message → announcement banner), plus SpaceHunter controls
(arcade toggle, force-start drop) and an audit log of every admin action."""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import String, cast, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.features import AdminAction, ArcadeResult, ButtonState, DropClaim
from app.models.game_state import GameState
from app.models.p2e import PromoCode, ReferralEarning
from app.models.user import User
from app.services import admin_state

router = APIRouter(prefix="/admin", tags=["Admin"])


def require_admin(admin_id: int) -> None:
    if not admin_state.is_admin(admin_id):
        raise HTTPException(status_code=403, detail="Admins only")


async def _log(db: AsyncSession, admin_id: int, action: str, target: str = "", detail: str = "") -> None:
    db.add(AdminAction(admin_id=admin_id, action=action, target=target, detail=detail))


class AdjustRequest(BaseModel):
    admin_id: int
    amount: int
    reason: str = Field(min_length=3, max_length=200)


class PromoCreateRequest(BaseModel):
    admin_id: int
    reward: int
    max_uses: int | None = None
    count: int = 1
    prefix: str = "PROMO"
    code: str | None = None


class SettingsRequest(BaseModel):
    admin_id: int
    referrals_enabled: bool | None = None
    arcade_enabled: bool | None = None
    announcement: str | None = None


class AdminOnly(BaseModel):
    admin_id: int


@router.get("/whoami")
async def whoami(telegram_id: int):
    return {"is_admin": admin_state.is_admin(telegram_id)}


@router.get("/announcement")
async def public_announcement(db: AsyncSession = Depends(get_db)):
    return {"text": await admin_state.announcement(db)}


@router.get("/stats")
async def stats(admin_id: int, db: AsyncSession = Depends(get_db)):
    require_admin(admin_id)
    users_count = int((await db.execute(select(func.count(User.id)))).scalar() or 0)
    lifetime = int((await db.execute(select(func.coalesce(func.sum(User.lifetime_earned), 0)))).scalar() or 0)
    ref_count = int((await db.execute(select(func.count(ReferralEarning.id)))).scalar() or 0)
    ref_paid = int((await db.execute(select(func.coalesce(func.sum(ReferralEarning.amount), 0)))).scalar() or 0)
    arcade_plays = int((await db.execute(select(func.count(ArcadeResult.id)))).scalar() or 0)
    arcade_paid = int((await db.execute(select(func.coalesce(func.sum(ArcadeResult.payout), 0)))).scalar() or 0)
    arcade_staked = int((await db.execute(select(func.coalesce(func.sum(ArcadeResult.stake), 0)))).scalar() or 0)
    btn = await db.get(ButtonState, 1)
    drop_claims = int((await db.execute(select(func.count(DropClaim.id)))).scalar() or 0)
    balances = int((await db.execute(select(func.coalesce(func.sum(GameState.balance), 0)))).scalar() or 0)
    from app.models.p2e import WithdrawalRequest
    pending_w = int((await db.execute(
        select(func.count(WithdrawalRequest.id)).where(WithdrawalRequest.status == "pending"))).scalar() or 0)
    paid_total = int((await db.execute(
        select(func.coalesce(func.sum(WithdrawalRequest.amount), 0))
        .where(WithdrawalRequest.status == "paid"))).scalar() or 0)
    banned_count = int((await db.execute(
        select(func.count(User.id)).where(User.banned.is_(True)))).scalar() or 0)
    return {
        "users": users_count,
        "balances_total": balances,
        "lifetime_earned_total": lifetime,
        "referral_payouts": ref_paid,
        "referral_events": ref_count,
        "arcade_plays": arcade_plays,
        "arcade_staked": arcade_staked,
        "arcade_paid": arcade_paid,
        "button_presses": int(btn.total_presses) if btn else 0,
        "drop_claims": drop_claims,
        "pending_withdrawals": pending_w,
        "paid_out_total": paid_total,
        "banned_users": banned_count,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _user_dict(u: User, invites: int = 0) -> dict:
    return {
        "telegram_id": int(u.telegram_id),
        "username": u.username,
        "balance": int(u.game_state.balance) if u.game_state else 0,
        "level": int(u.game_state.level) if u.game_state else 1,
        "lifetime_earned": int(u.lifetime_earned or 0),
        "lifetime_mined": int(u.lifetime_mined or 0),
        "referral_earnings": int(u.referral_earnings or 0),
        "task_boost_pct": float(u.game_state.task_boost_pct or 0) if u.game_state else 0,
        "admin_boost_pct": float(u.game_state.admin_boost_pct or 0) if u.game_state else 0,
        "wallet": u.ton_wallet_address,
        "banned": bool(u.banned),
        "ban_reason": u.ban_reason,
        "invites": invites,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


@router.get("/users")
async def list_users(admin_id: int, q: str = "", limit: int = 50, db: AsyncSession = Depends(get_db)):
    require_admin(admin_id)
    limit = min(max(int(limit), 1), 200)
    stmt = select(User).options(selectinload(User.game_state)).order_by(User.lifetime_earned.desc())
    if q:
        stmt = stmt.where(or_(
            User.username.ilike(f"%{q}%"),
            cast(User.telegram_id, String).like(f"%{q}%"),
        ))
    stmt = stmt.limit(limit)
    users = (await db.execute(stmt)).scalars().all()
    return {"users": [_user_dict(u) for u in users]}


@router.get("/users/{tid}")
async def user_detail(tid: int, admin_id: int, db: AsyncSession = Depends(get_db)):
    require_admin(admin_id)
    result = await db.execute(
        select(User).options(selectinload(User.game_state)).where(User.telegram_id == tid)
    )
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    invites = int((await db.execute(
        select(func.count(User.id)).where(User.referred_by_id == u.id))).scalar() or 0)
    arcade = (await db.execute(
        select(func.count(ArcadeResult.id), func.coalesce(func.sum(ArcadeResult.payout), 0),
               func.coalesce(func.sum(ArcadeResult.stake), 0)).where(ArcadeResult.user_id == u.id)
    )).one()
    d = _user_dict(u, invites)
    d["arcade_plays"] = int(arcade[0] or 0)
    d["arcade_won"] = int(arcade[1] or 0)
    d["arcade_staked"] = int(arcade[2] or 0)
    if u.referred_by_id:
        ref_tid = (await db.execute(
            select(User.telegram_id).where(User.id == u.referred_by_id))).scalar_one_or_none()
        d["referrer_telegram_id"] = int(ref_tid) if ref_tid else None
    else:
        d["referrer_telegram_id"] = None
    from app.models.p2e import WithdrawalRequest
    wrows = (await db.execute(
        select(WithdrawalRequest).where(WithdrawalRequest.user_id == u.id)
        .order_by(WithdrawalRequest.created_at.desc()).limit(5))).scalars().all()
    d["recent_withdrawals"] = [
        {"id": w.id, "amount": int(w.amount), "status": w.status,
         "created_at": w.created_at.isoformat() if w.created_at else None}
        for w in wrows
    ]
    return d


@router.post("/users/{tid}/adjust")
async def adjust_balance(tid: int, req: AdjustRequest, db: AsyncSession = Depends(get_db)):
    require_admin(req.admin_id)
    if not (-1_000_000 <= req.amount <= 1_000_000):
        raise HTTPException(status_code=400, detail="Amount out of range (±1,000,000)")
    result = await db.execute(
        select(User).options(selectinload(User.game_state)).where(User.telegram_id == tid)
    )
    u = result.scalar_one_or_none()
    if not u or not u.game_state:
        raise HTTPException(status_code=404, detail="User not found")
    # Atomic expression update (floored at 0) — no read-modify-write race,
    # and the audit log records the balance this actually produced.
    await db.execute(
        update(GameState)
        .where(GameState.user_id == u.id)
        .values(balance=func.max(0, GameState.balance + req.amount))
    )
    await db.refresh(u.game_state)
    await _log(db, req.admin_id, "adjust_balance", str(tid),
               f"{req.amount:+d} CSM → balance {int(u.game_state.balance)} — {req.reason}")
    await db.commit()
    await db.refresh(u.game_state)
    return {"telegram_id": tid, "balance": int(u.game_state.balance)}


@router.get("/settings")
async def get_settings(admin_id: int, db: AsyncSession = Depends(get_db)):
    require_admin(admin_id)
    return {
        "referrals_enabled": await admin_state.referrals_enabled(db),
        "arcade_enabled": await admin_state.arcade_enabled(db),
        "announcement": await admin_state.announcement(db),
    }


@router.post("/settings")
async def update_settings(req: SettingsRequest, db: AsyncSession = Depends(get_db)):
    require_admin(req.admin_id)
    if req.referrals_enabled is not None:
        await admin_state.set_setting(db, "referrals_enabled", "1" if req.referrals_enabled else "0")
        await _log(db, req.admin_id, "toggle_referrals", "", "on" if req.referrals_enabled else "off")
    if req.arcade_enabled is not None:
        await admin_state.set_setting(db, "arcade_enabled", "1" if req.arcade_enabled else "0")
        await _log(db, req.admin_id, "toggle_arcade", "", "on" if req.arcade_enabled else "off")
    if req.announcement is not None:
        import html as _html
        await admin_state.set_setting(db, "announcement", _html.escape(req.announcement.strip()[:280], quote=True))
        await _log(db, req.admin_id, "set_announcement", "", req.announcement.strip()[:60])
    await db.commit()
    return await get_settings(req.admin_id, db)


@router.post("/drops/force-start")
async def force_start_drop(req: AdminOnly, db: AsyncSession = Depends(get_db)):
    require_admin(req.admin_id)
    now = datetime.now(timezone.utc)
    # Unpredictable key (was a bare Unix timestamp anyone could compute).
    key = f"forced-{secrets.token_urlsafe(12)}"
    until = int((now + timedelta(minutes=15)).timestamp())
    await admin_state.set_setting(db, "drop_force_key", key)
    await admin_state.set_setting(db, "drop_force_until", str(until))
    await _log(db, req.admin_id, "force_start_drop", key, "live for 15 minutes")
    await db.commit()
    return {"drop_key": key, "ends_at": datetime.fromtimestamp(until, tz=timezone.utc).isoformat()}


@router.get("/actions")
async def list_actions(admin_id: int, q: str = "", limit: int = 50, db: AsyncSession = Depends(get_db)):
    require_admin(admin_id)
    limit = min(max(int(limit), 1), 200)
    stmt = select(AdminAction).order_by(AdminAction.id.desc())
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(
            AdminAction.action.ilike(like),
            AdminAction.target.ilike(like),
            AdminAction.detail.ilike(like),
        ))
    rows = (await db.execute(stmt.limit(limit))).scalars().all()
    return {"actions": [{
        "id": a.id,
        "action": a.action, "target": a.target, "detail": a.detail,
        "at": a.created_at.isoformat() if a.created_at else None,
    } for a in rows]}
