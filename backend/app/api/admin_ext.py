"""Admin panel expansion — player management actions, withdrawal review
queue with proof posting, task manager, economy tunables, comms
(announcement channel proofs + broadcast), audit export.

Every action is allowlist-gated (require_admin) and written to the admin
audit log. Money movements use atomic SQL-side credits only.
"""
import asyncio
import html as _html
import json as _json
import time as _time
import urllib.request
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.admin import _log, require_admin
from app.models.features import AdminAction
from app.database import get_db
from app.models.game_state import GameState
from app.models.p2e import BotStart, ReferralEarning, WithdrawalRequest
from app.models.task import Task
from app.models.user import User
from app.models.user_tasks import UserTask
from app.services import admin_state
from app.services.auth import _bot_token
from app.services.p2e import (
    MINING_BASE_RATE,
    MINING_SESSION_SECONDS,
    OG_PASS_COST,
    WELCOME_REWARD,
    atomic_credit,
    econ_int,
)

router = APIRouter(prefix="/admin", tags=["AdminPanel"])


async def _get_user(db: AsyncSession, tid: int) -> User:
    result = await db.execute(
        select(User).options(selectinload(User.game_state)).where(User.telegram_id == tid)
    )
    u = result.scalar_one_or_none()
    if not u or not u.game_state:
        raise HTTPException(status_code=404, detail="User not found")
    return u


# ------------------------------------------------------------- player actions

class LevelRequest(BaseModel):
    admin_id: int
    level: int


class BoostGrantRequest(BaseModel):
    admin_id: int
    pct: float


class GrantReferralRequest(BaseModel):
    admin_id: int
    amount: int


class SetReferrerRequest(BaseModel):
    admin_id: int
    referrer_telegram_id: int | None = None


class BanRequest(BaseModel):
    admin_id: int
    reason: str = ""


@router.post("/users/{tid}/set-level")
async def set_level(tid: int, req: LevelRequest, db: AsyncSession = Depends(get_db)):
    require_admin(req.admin_id)
    if not (1 <= req.level <= 100):
        raise HTTPException(status_code=400, detail="Level must be 1..100")
    u = await _get_user(db, tid)
    await db.execute(
        update(GameState).where(GameState.user_id == u.id).values(level=req.level)
    )
    await _log(db, req.admin_id, "set_level", str(tid), f"level → {req.level}")
    await db.commit()
    return {"telegram_id": tid, "level": req.level}


@router.post("/users/{tid}/grant-boost")
async def grant_boost(tid: int, req: BoostGrantRequest, db: AsyncSession = Depends(get_db)):
    require_admin(req.admin_id)
    if not (-90 <= req.pct <= 500):
        raise HTTPException(status_code=400, detail="Boost must be -90..+500%")
    u = await _get_user(db, tid)
    await db.execute(
        update(GameState).where(GameState.user_id == u.id).values(admin_boost_pct=float(req.pct))
    )
    await _log(db, req.admin_id, "grant_boost", str(tid), f"admin mining boost → {req.pct:+}%")
    await db.commit()
    return {"telegram_id": tid, "admin_boost_pct": req.pct}


@router.post("/users/{tid}/grant-referral-bonus")
async def grant_referral_bonus(tid: int, req: GrantReferralRequest, db: AsyncSession = Depends(get_db)):
    require_admin(req.admin_id)
    if not (1 <= req.amount <= 100_000):
        raise HTTPException(status_code=400, detail="Amount must be 1..100,000")
    u = await _get_user(db, tid)
    # Ledger-labelled admin grant: visible in the player's crew earnings as
    # an admin grant, never disguised as an organic referral payout.
    await atomic_credit(db, u, req.amount, referral_delta=req.amount)
    db.add(ReferralEarning(referrer_id=u.id, from_user_id=u.id, amount=req.amount, tier=0, kind="admin_grant"))
    await _log(db, req.admin_id, "grant_referral_bonus", str(tid), f"+{req.amount} CSM (admin grant)")
    await db.commit()
    await db.refresh(u.game_state)
    return {"telegram_id": tid, "balance": int(u.game_state.balance)}


@router.post("/users/{tid}/set-referrer")
async def set_referrer(tid: int, req: SetReferrerRequest, db: AsyncSession = Depends(get_db)):
    require_admin(req.admin_id)
    u = await _get_user(db, tid)
    if req.referrer_telegram_id is None:
        u.referred_by_id = None
        await _log(db, req.admin_id, "set_referrer", str(tid), "referrer cleared")
        await db.commit()
        return {"telegram_id": tid, "referrer_telegram_id": None}
    if req.referrer_telegram_id == tid:
        raise HTTPException(status_code=400, detail="A user cannot refer themselves")
    ref = await _get_user(db, req.referrer_telegram_id)
    # Cycle guard: the new referrer's own chain must not lead back to u.
    # Walk to the root — a depth cap that silently stops would fall through
    # and CREATE the cycle on chains deeper than the cap, so hitting the
    # safety bound (or an existing loop) refuses the relink instead.
    seen, cursor = set(), ref
    while cursor is not None and cursor.referred_by_id is not None:
        if cursor.id in seen:
            raise HTTPException(status_code=400, detail="Existing referral cycle detected")
        seen.add(cursor.id)
        if len(seen) > 10000:
            raise HTTPException(status_code=400, detail="Referral chain too deep to verify")
        if cursor.referred_by_id == u.id:
            raise HTTPException(status_code=400, detail="That would create a referral cycle")
        nxt = await db.execute(select(User).where(User.id == cursor.referred_by_id))
        cursor = nxt.scalar_one_or_none()
    u.referred_by_id = ref.id
    await _log(db, req.admin_id, "set_referrer", str(tid), f"referrer → {req.referrer_telegram_id}")
    await db.commit()
    return {"telegram_id": tid, "referrer_telegram_id": req.referrer_telegram_id}


@router.post("/users/{tid}/ban")
async def ban_user(tid: int, req: BanRequest, db: AsyncSession = Depends(get_db)):
    require_admin(req.admin_id)
    if admin_state.is_admin(tid):
        raise HTTPException(status_code=400, detail="Admins cannot be banned")
    u = await _get_user(db, tid)
    reason = (req.reason or "").strip()[:200]
    await db.execute(
        update(User).where(User.id == u.id).values(banned=True, ban_reason=reason or None)
    )
    await _log(db, req.admin_id, "ban_user", str(tid), reason or "no reason given")
    await db.commit()
    return {"telegram_id": tid, "banned": True}


@router.post("/users/{tid}/unban")
async def unban_user(tid: int, req: BanRequest, db: AsyncSession = Depends(get_db)):
    require_admin(req.admin_id)
    u = await _get_user(db, tid)
    await db.execute(
        update(User).where(User.id == u.id).values(banned=False, ban_reason=None)
    )
    await _log(db, req.admin_id, "unban_user", str(tid), "")
    await db.commit()
    return {"telegram_id": tid, "banned": False}


# ---------------------------------------------------------------- withdrawals

def _withdrawal_dict(w: WithdrawalRequest, u: User | None) -> dict:
    return {
        "id": w.id,
        "telegram_id": int(u.telegram_id) if u else None,
        "username": u.username if u else None,
        "amount": int(w.amount),
        "address": w.address,
        "status": w.status,
        "created_at": w.created_at.isoformat() if w.created_at else None,
        "reviewed_by": w.reviewed_by,
        "reviewed_at": w.reviewed_at.isoformat() if w.reviewed_at else None,
        "tx_hash": w.tx_hash,
        "paid_at": w.paid_at.isoformat() if w.paid_at else None,
    }


@router.get("/withdrawals")
async def list_withdrawals(admin_id: int, status: str = "", limit: int = 100,
                           db: AsyncSession = Depends(get_db)):
    require_admin(admin_id)
    limit = min(max(int(limit), 1), 200)
    stmt = (select(WithdrawalRequest, User)
            .join(User, User.id == WithdrawalRequest.user_id)
            .order_by(WithdrawalRequest.created_at.desc()))
    if status:
        stmt = stmt.where(WithdrawalRequest.status == status)
    rows = (await db.execute(stmt.limit(limit))).all()
    counts = dict((await db.execute(
        select(WithdrawalRequest.status, func.count(WithdrawalRequest.id))
        .group_by(WithdrawalRequest.status))).all())
    paid_total = (await db.execute(
        select(func.coalesce(func.sum(WithdrawalRequest.amount), 0))
        .where(WithdrawalRequest.status == "paid"))).scalar() or 0
    return {
        "withdrawals": [_withdrawal_dict(w, u) for w, u in rows],
        "counts": {k: int(v) for k, v in counts.items()},
        "paid_total": int(paid_total),
    }


class ReviewRequest(BaseModel):
    admin_id: int
    action: str  # approve | reject


class MarkPaidRequest(BaseModel):
    admin_id: int
    tx_hash: str


async def _get_withdrawal(db: AsyncSession, wid: int) -> WithdrawalRequest:
    w = (await db.execute(
        select(WithdrawalRequest).where(WithdrawalRequest.id == wid))).scalar_one_or_none()
    if not w:
        raise HTTPException(status_code=404, detail="Withdrawal not found")
    return w


@router.post("/withdrawals/{wid}/review")
async def review_withdrawal(wid: int, req: ReviewRequest, db: AsyncSession = Depends(get_db)):
    require_admin(req.admin_id)
    if req.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action must be approve or reject")
    w = await _get_withdrawal(db, wid)
    new_status = "approved" if req.action == "approve" else "rejected"
    # Guarded status flip: only the transaction that moves pending -> final
    # proceeds. A concurrent double-click loses the flip (rowcount 0) and can
    # never reach the refund below, so the escrow is refunded at most once.
    flip = await db.execute(
        update(WithdrawalRequest)
        .where(WithdrawalRequest.id == wid, WithdrawalRequest.status == "pending")
        .values(status=new_status, reviewed_by=req.admin_id, reviewed_at=datetime.now()))
    if flip.rowcount != 1:
        await db.rollback()
        current = (await db.execute(
            select(WithdrawalRequest.status).where(WithdrawalRequest.id == wid))).scalar_one_or_none()
        raise HTTPException(status_code=400, detail=f"Already {current or w.status}")
    if req.action == "approve":
        await _log(db, req.admin_id, "withdraw_approve", str(w.user_id), f"#{wid} {w.amount} CSM")
    else:
        # The request debited the amount into escrow — rejection refunds it.
        owner = (await db.execute(
            select(User).options(selectinload(User.game_state)).where(User.id == w.user_id))).scalar_one()
        await atomic_credit(db, owner, int(w.amount), count_lifetime=False)
        await _log(db, req.admin_id, "withdraw_reject_refund", str(w.user_id), f"#{wid} {w.amount} CSM refunded")
    await db.commit()
    return {"id": wid, "status": new_status}


def _send_telegram(chat_id: str, text: str) -> bool:
    """One Bot API sendMessage. Runs in a thread (blocking urllib)."""
    token = _bot_token()
    if not token or not chat_id:
        return False
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=_json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                              "disable_web_page_preview": True}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            return bool(_json.loads(r.read() or b"{}").get("ok"))
    except Exception:
        return False


async def _post_payout_proof(db: AsyncSession, w: WithdrawalRequest, u: User) -> bool:
    """Post a REAL payout proof (from the paid record + its tx hash) to the
    configured proofs channel. Only ever called with a genuinely paid row."""
    channel = await admin_state.get_setting(db, "proofs_channel_id", "")
    realtime = await admin_state.get_setting(db, "proofs_realtime", "1")
    if not channel or realtime == "0":
        return False
    addr = w.address or ""
    masked = f"{addr[:6]}…{addr[-4:]}" if len(addr) > 12 else addr
    tx = (w.tx_hash or "").strip()
    tx_line = ""
    if tx:
        link = tx if tx.startswith("http") else f"https://tonviewer.io/transaction/{tx}"
        tx_line = f"\nTransaction: <a href=\"{_html.escape(link, quote=True)}\">tonviewer</a>"
    text = (f"💸 <b>Payout sent</b>\n\n"
            f"Amount: <b>{int(w.amount):,} CSM</b>\n"
            f"Wallet: <code>{_html.escape(masked)}</code>"
            f"{tx_line}")
    return await asyncio.to_thread(_send_telegram, channel, text)


@router.post("/withdrawals/{wid}/mark-paid")
async def mark_paid(wid: int, req: MarkPaidRequest, db: AsyncSession = Depends(get_db)):
    require_admin(req.admin_id)
    tx = (req.tx_hash or "").strip()
    if len(tx) < 8:
        raise HTTPException(status_code=400, detail="A transaction hash or link is required")
    w = await _get_withdrawal(db, wid)
    # Guarded flip for the same reason as review: two concurrent mark-paid
    # calls must not both post a proof or overwrite the tx hash.
    flip = await db.execute(
        update(WithdrawalRequest)
        .where(WithdrawalRequest.id == wid, WithdrawalRequest.status == "approved")
        .values(status="paid", tx_hash=tx[:256], paid_at=datetime.now()))
    if flip.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Only an approved withdrawal can be marked paid")
    owner = (await db.execute(select(User).where(User.id == w.user_id))).scalar_one()
    await _log(db, req.admin_id, "withdraw_paid", str(w.user_id), f"#{wid} {w.amount} CSM tx {tx[:24]}")
    await db.commit()
    await db.refresh(w)
    proof = await _post_payout_proof(db, w, owner)
    return {"id": wid, "status": "paid", "proof_posted": proof}


# ------------------------------------------------------------------ tasks

_ALLOWED_CONDITIONS = {
    "level", "passive_income", "balance", "mining_sessions", "mining_claims",
    "referrals", "bot_started", "wallet_connected",
    "taps", "energy_spent", "daily_balance",
}


def _task_dict(t: Task) -> dict:
    return {
        "id": t.id, "title": t.title, "description": t.description, "type": t.type,
        "reward": int(t.reward or 0), "reward_type": t.reward_type or "token",
        "multiplier_pct": float(t.multiplier_pct or 0), "link_url": t.link_url,
        "condition_type": t.condition_type, "condition_value": int(t.condition_value or 0),
        "is_active": bool(t.is_active),
    }


def _validate_task_fields(type_: str, reward_type: str, reward: int,
                          multiplier_pct: float, condition_type: str, condition_value: int) -> None:
    if condition_type not in _ALLOWED_CONDITIONS:
        raise HTTPException(status_code=400, detail="Unknown condition_type")
    if type_ not in ("permanent", "daily"):
        raise HTTPException(status_code=400, detail="type must be permanent or daily")
    if reward_type not in ("token", "multiplier"):
        raise HTTPException(status_code=400, detail="reward_type must be token or multiplier")
    if not (0 <= reward <= 100_000):
        raise HTTPException(status_code=400, detail="reward out of range")
    if not (0 <= multiplier_pct <= 100):
        raise HTTPException(status_code=400, detail="multiplier_pct out of range")
    if not (0 <= condition_value <= 10_000_000):
        raise HTTPException(status_code=400, detail="condition_value out of range")


class AdminTaskCreate(BaseModel):
    admin_id: int
    title: str
    description: str = ""
    type: str = "permanent"
    reward: int = 0
    reward_type: str = "token"
    multiplier_pct: float = 0
    link_url: str | None = None
    condition_type: str
    condition_value: int


class AdminTaskPatch(BaseModel):
    admin_id: int
    title: str | None = None
    description: str | None = None
    reward: int | None = None
    multiplier_pct: float | None = None
    condition_value: int | None = None
    link_url: str | None = None
    is_active: bool | None = None


@router.get("/tasks/all")
async def list_all_tasks(admin_id: int, db: AsyncSession = Depends(get_db)):
    require_admin(admin_id)
    tasks = (await db.execute(select(Task).order_by(Task.id))).scalars().all()
    return {"tasks": [_task_dict(t) for t in tasks]}


@router.post("/tasks/create")
async def create_task_admin(req: AdminTaskCreate, db: AsyncSession = Depends(get_db)):
    require_admin(req.admin_id)
    _validate_task_fields(req.type, req.reward_type, req.reward, req.multiplier_pct,
                          req.condition_type, req.condition_value)
    t = Task(title=req.title.strip()[:120], description=req.description.strip()[:300],
             type=req.type, reward=req.reward, reward_type=req.reward_type,
             multiplier_pct=req.multiplier_pct, link_url=req.link_url,
             condition_type=req.condition_type, condition_value=req.condition_value,
             is_active=True)
    db.add(t)
    await _log(db, req.admin_id, "task_create", "", req.title[:60])
    await db.commit()
    await db.refresh(t)
    return _task_dict(t)


@router.patch("/tasks/{task_id}")
async def patch_task(task_id: int, req: AdminTaskPatch, db: AsyncSession = Depends(get_db)):
    require_admin(req.admin_id)
    t = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    if req.reward is not None and not (0 <= req.reward <= 100_000):
        raise HTTPException(status_code=400, detail="reward out of range")
    if req.multiplier_pct is not None and not (0 <= req.multiplier_pct <= 100):
        raise HTTPException(status_code=400, detail="multiplier_pct out of range")
    if req.condition_value is not None and not (0 <= req.condition_value <= 10_000_000):
        raise HTTPException(status_code=400, detail="condition_value out of range")
    for field in ("title", "description", "reward", "multiplier_pct", "condition_value", "link_url", "is_active"):
        val = getattr(req, field)
        if val is not None:
            setattr(t, field, val)
    await _log(db, req.admin_id, "task_update", str(task_id), t.title[:60])
    await db.commit()
    return _task_dict(t)


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: int, admin_id: int, db: AsyncSession = Depends(get_db)):
    require_admin(admin_id)
    t = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    title = (t.title or "")[:60]
    await db.execute(UserTask.__table__.delete().where(UserTask.task_id == task_id))
    await db.delete(t)
    await _log(db, admin_id, "task_delete", str(task_id), title)
    await db.commit()
    return {"deleted": task_id}


# ------------------------------------------------------------------ economy

class EconomyRequest(BaseModel):
    admin_id: int
    base_rate: int | None = None
    session_hours: int | None = None
    og_cost: int | None = None
    welcome_reward: int | None = None


@router.get("/economy")
async def get_economy(admin_id: int, db: AsyncSession = Depends(get_db)):
    require_admin(admin_id)
    return {
        "base_rate": await econ_int(db, "econ_base_rate", MINING_BASE_RATE),
        "session_hours": await econ_int(db, "econ_session_hours", MINING_SESSION_SECONDS // 3600),
        "og_cost": await econ_int(db, "econ_og_cost", OG_PASS_COST),
        "welcome_reward": await econ_int(db, "econ_welcome_reward", WELCOME_REWARD),
    }


@router.post("/economy")
async def set_economy(req: EconomyRequest, db: AsyncSession = Depends(get_db)):
    require_admin(req.admin_id)
    bounds = {"base_rate": (1, 10_000), "session_hours": (1, 72),
              "og_cost": (100, 1_000_000), "welcome_reward": (0, 10_000)}
    keys = {"base_rate": "econ_base_rate", "session_hours": "econ_session_hours",
            "og_cost": "econ_og_cost", "welcome_reward": "econ_welcome_reward"}
    defaults = {"base_rate": MINING_BASE_RATE,
                "session_hours": MINING_SESSION_SECONDS // 3600,
                "og_cost": OG_PASS_COST,
                "welcome_reward": WELCOME_REWARD}
    for field, (lo, hi) in bounds.items():
        val = getattr(req, field)
        if val is not None:
            if not (lo <= val <= hi):
                raise HTTPException(status_code=400, detail=f"{field} must be {lo}..{hi}")
            old = await econ_int(db, keys[field], defaults[field])
            await admin_state.set_setting(db, keys[field], str(val))
            await _log(db, req.admin_id, "economy_set", field, f"{old} -> {val}")
    await db.commit()
    return await get_economy(req.admin_id, db)


class EconomyRollbackRequest(BaseModel):
    admin_id: int
    action_id: int


@router.post("/economy/rollback")
async def rollback_economy(req: EconomyRollbackRequest, db: AsyncSession = Depends(get_db)):
    """Revert ONE past economy change, identified by its audit-log entry.

    economy_set entries store detail as "old -> new" with target = field, so
    the pre-change value is recoverable from the log itself. The rollback is
    bounds-checked and written to the audit log as its own entry, so the
    history stays append-only and honest.
    """
    require_admin(req.admin_id)
    entry = (await db.execute(
        select(AdminAction).where(AdminAction.id == req.action_id))).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Audit entry not found")
    if entry.action != "economy_set":
        raise HTTPException(status_code=400, detail="Only economy_set entries can be rolled back")
    bounds = {"base_rate": (1, 10_000), "session_hours": (1, 72),
              "og_cost": (100, 1_000_000), "welcome_reward": (0, 10_000)}
    keys = {"base_rate": "econ_base_rate", "session_hours": "econ_session_hours",
            "og_cost": "econ_og_cost", "welcome_reward": "econ_welcome_reward"}
    defaults = {"base_rate": MINING_BASE_RATE,
                "session_hours": MINING_SESSION_SECONDS // 3600,
                "og_cost": OG_PASS_COST,
                "welcome_reward": WELCOME_REWARD}
    field = entry.target
    if field not in bounds:
        raise HTTPException(status_code=400, detail=f"Unknown economy field {field!r}")
    try:
        old_val = int(str(entry.detail).split(" -> ")[0].strip())
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="Audit entry has no recoverable previous value")
    lo, hi = bounds[field]
    if not (lo <= old_val <= hi):
        raise HTTPException(status_code=400, detail=f"Recorded previous value {old_val} is out of bounds")
    current = await econ_int(db, keys[field], defaults[field])
    if current == old_val:
        raise HTTPException(status_code=400, detail=f"{field} is already {old_val} — nothing to roll back")
    await admin_state.set_setting(db, keys[field], str(old_val))
    await _log(db, req.admin_id, "economy_rollback", field, f"{current} -> {old_val} (reverts #{entry.id})")
    await db.commit()
    return await get_economy(req.admin_id, db)


# ------------------------------------------------------------------ comms

class CommsRequest(BaseModel):
    admin_id: int
    proofs_channel_id: str | None = None
    proofs_realtime: bool | None = None
    digest_enabled: bool | None = None
    digest_hour_utc: int | None = None


@router.get("/comms")
async def get_comms(admin_id: int, db: AsyncSession = Depends(get_db)):
    require_admin(admin_id)
    return {
        "proofs_channel_id": await admin_state.get_setting(db, "proofs_channel_id", ""),
        "proofs_realtime": (await admin_state.get_setting(db, "proofs_realtime", "1")) == "1",
        "digest_enabled": (await admin_state.get_setting(db, "digest_enabled", "0")) == "1",
        "digest_hour_utc": int((await admin_state.get_setting(db, "digest_hour_utc", "12")) or 12),
        "bot_audience": int((await db.execute(select(func.count(BotStart.telegram_id)))).scalar() or 0),
    }


@router.post("/comms")
async def set_comms(req: CommsRequest, db: AsyncSession = Depends(get_db)):
    require_admin(req.admin_id)
    if req.proofs_channel_id is not None:
        await admin_state.set_setting(db, "proofs_channel_id", req.proofs_channel_id.strip()[:64])
    if req.proofs_realtime is not None:
        await admin_state.set_setting(db, "proofs_realtime", "1" if req.proofs_realtime else "0")
    if req.digest_enabled is not None:
        await admin_state.set_setting(db, "digest_enabled", "1" if req.digest_enabled else "0")
    if req.digest_hour_utc is not None:
        if not (0 <= req.digest_hour_utc <= 23):
            raise HTTPException(status_code=400, detail="digest_hour_utc must be 0..23")
        await admin_state.set_setting(db, "digest_hour_utc", str(req.digest_hour_utc))
    await _log(db, req.admin_id, "comms_set", "", "")
    await db.commit()
    return await get_comms(req.admin_id, db)


class BroadcastRequest(BaseModel):
    admin_id: int
    text: str


@router.post("/broadcast")
async def broadcast(req: BroadcastRequest, db: AsyncSession = Depends(get_db)):
    require_admin(req.admin_id)
    text = (req.text or "").strip()
    if not text or len(text) > 1000:
        raise HTTPException(status_code=400, detail="Message must be 1..1000 characters")
    ids = (await db.execute(select(BotStart.telegram_id))).scalars().all()
    safe = _html.escape(text)
    message = f"📣 <b>Gradient Farming</b>\n\n{safe}"

    def _send_all() -> tuple[int, int]:
        ok = fail = 0
        for tid in ids[:5000]:
            if _send_telegram(str(tid), message):
                ok += 1
            else:
                fail += 1
            _time.sleep(0.05)  # stay well under Bot API rate limits
        return ok, fail

    sent, failed = await asyncio.to_thread(_send_all)
    await _log(db, req.admin_id, "broadcast", "", f"{sent} sent, {failed} failed: {text[:40]}")
    await db.commit()
    return {"audience": len(ids), "sent": sent, "failed": failed}


# ------------------------------------------------------------------ audit export

@router.get("/actions/export")
async def export_actions(admin_id: int, db: AsyncSession = Depends(get_db)):
    require_admin(admin_id)
    from app.models.features import AdminAction
    rows = (await db.execute(
        select(AdminAction).order_by(AdminAction.created_at.desc()).limit(2000))).scalars().all()
    lines = ["created_at,admin_id,action,target,detail"]
    for r in rows:
        def cell(v) -> str:
            s = str(v or "")
            # Spreadsheet formula-injection guard: a cell starting with a
            # formula character is data here, never a formula.
            if s[:1] in ("=", "+", "-", "@", "\t", "\r"):
                s = "'" + s
            return '"' + s.replace('"', '""') + '"'
        lines.append(",".join([str(r.created_at), str(r.admin_id), cell(r.action), cell(r.target), cell(r.detail)]))
    return PlainTextResponse("\n".join(lines), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=admin-actions.csv"})


@router.get("/export.xlsx")
async def export_workbook(admin_id: int, db: AsyncSession = Depends(get_db)):
    require_admin(admin_id)
    from fastapi import Response
    from app.services.export_xlsx import build_workbook
    data = await build_workbook(db)
    return Response(content=data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=spacehunter-export.xlsx"})
