"""Excel workbook export for admin reporting."""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import text

HDR_FILL = PatternFill("solid", fgColor="06070C")
HDR_FONT = Font(bold=True, color="F5C518")


def _safe(v: Any) -> Any:
    """Neutralise spreadsheet formula injection in text values."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@"):
        return "'" + v
    return v


def _row(ws, values: Iterable[Any]) -> None:
    ws.append([_safe(v) for v in values])


def _finish(ws, widths: Sequence[int]) -> None:
    for row in ws.iter_rows(min_row=1, max_row=1):
        for cell in row:
            cell.fill = HDR_FILL
            cell.font = HDR_FONT
    ws.freeze_panes = "A2"
    last = get_column_letter(max(ws.max_column, 1))
    ws.auto_filter.ref = f"A1:{last}{max(ws.max_row, 1)}"
    for idx, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width


async def _scalar(db, sql: str, **params: Any) -> Any:
    value = (await db.execute(text(sql), params)).scalar()
    return 0 if value is None else value


async def _build_summary(db, wb: Workbook) -> None:
    ws = wb.create_sheet("Summary")
    _row(ws, ["Metric", "Value"])

    players = await _scalar(db, "SELECT COUNT(*) FROM users")
    balances = await _scalar(db, "SELECT COALESCE(SUM(balance), 0) FROM game_states")
    mined = await _scalar(db, "SELECT COALESCE(SUM(lifetime_mined), 0) FROM users")
    pend_count, pend_sum = (await db.execute(text(
        "SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM withdrawal_requests "
        "WHERE status = :s"), {"s": "pending"})).one()
    paid_count, paid_sum = (await db.execute(text(
        "SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM withdrawal_requests "
        "WHERE status = :s"), {"s": "paid"})).one()
    referral_sum = await _scalar(
        db, "SELECT COALESCE(SUM(amount), 0) FROM referral_earnings_ledger")

    _row(ws, ["Generated at", datetime.now(timezone.utc).isoformat(timespec="seconds")])
    _row(ws, ["Total players", players])
    _row(ws, ["Total CSM in balances", balances])
    _row(ws, ["Total lifetime mined", mined])
    _row(ws, ["Withdrawals pending (count)", pend_count])
    _row(ws, ["Withdrawals pending (CSM)", pend_sum])
    _row(ws, ["Withdrawals paid (count)", paid_count])
    _row(ws, ["Withdrawals paid (CSM)", paid_sum])
    _row(ws, ["Referral earnings paid", referral_sum])
    _finish(ws, [34, 28])


async def _build_players(db, wb: Workbook) -> None:
    ws = wb.create_sheet("Players")
    _row(ws, ["Telegram ID", "Username", "Balance", "Lifetime mined",
              "Lifetime earned", "Referral earnings", "Invited by TG", "Banned", "Joined"])

    result = await db.execute(text(
        "SELECT u.telegram_id, u.username, gs.balance, u.lifetime_mined, "
        "u.lifetime_earned, u.referral_earnings, ref.telegram_id AS invited_by_tg, "
        "u.banned, u.created_at "
        "FROM users AS u "
        "LEFT JOIN game_states AS gs ON gs.user_id = u.id "
        "LEFT JOIN users AS ref ON ref.id = u.referred_by_id "
        "ORDER BY COALESCE(gs.balance, 0) DESC, u.id ASC"))

    for telegram_id, username, balance, mined, earned, ref_earn, invited_by, banned, joined \
            in result.all():
        _row(ws, [telegram_id, username, balance, mined, earned, ref_earn,
                  invited_by, "Yes" if banned else "No", joined])

    _finish(ws, [16, 24, 14, 16, 16, 18, 16, 10, 26])


async def _build_withdrawals(db, wb: Workbook) -> None:
    ws = wb.create_sheet("Withdrawals")
    _row(ws, ["ID", "Player", "Telegram ID", "Amount CSM", "Wallet address",
              "Status", "Requested", "Reviewed by", "Reviewed at", "Paid at", "Tx hash"])

    result = await db.execute(text(
        "SELECT w.id, u.username, u.telegram_id, w.amount, w.address, w.status, "
        "w.created_at, w.reviewed_by, w.reviewed_at, w.paid_at, w.tx_hash "
        "FROM withdrawal_requests AS w "
        "LEFT JOIN users AS u ON u.id = w.user_id "
        "ORDER BY w.id DESC"))

    for wid, player, telegram_id, amount, address, status, requested, \
            reviewed_by, reviewed_at, paid_at, tx_hash in result.all():
        _row(ws, [wid, player, telegram_id, amount, address, status, requested,
                  reviewed_by, reviewed_at, paid_at, tx_hash])

    _finish(ws, [10, 24, 16, 14, 46, 12, 26, 16, 26, 26, 70])


async def _build_referrals(db, wb: Workbook) -> None:
    ws = wb.create_sheet("Referral Ledger")
    _row(ws, ["ID", "Referrer", "Referrer TG", "From player", "From TG",
              "Tier", "Kind", "Amount", "Date"])

    result = await db.execute(text(
        "SELECT l.id, ref.username, ref.telegram_id, src.username, src.telegram_id, "
        "l.tier, l.kind, l.amount, l.created_at "
        "FROM referral_earnings_ledger AS l "
        "LEFT JOIN users AS ref ON ref.id = l.referrer_id "
        "LEFT JOIN users AS src ON src.id = l.from_user_id "
        "ORDER BY l.id DESC"))

    for lid, referrer, referrer_tg, from_player, from_tg, tier, kind, amount, created \
            in result.all():
        _row(ws, [lid, referrer, referrer_tg, from_player, from_tg,
                  tier, kind, amount, created])

    _finish(ws, [10, 24, 16, 24, 16, 8, 14, 14, 26])


async def _build_admin_actions(db, wb: Workbook) -> None:
    ws = wb.create_sheet("Admin Actions")
    _row(ws, ["ID", "Admin TG", "Action", "Target", "Detail", "Date"])

    result = await db.execute(text(
        "SELECT id, admin_id, action, target, detail, created_at "
        "FROM admin_actions ORDER BY id DESC"))

    for aid, admin_tg, action, target, detail, created in result.all():
        _row(ws, [aid, admin_tg, action, target, detail, created])

    _finish(ws, [10, 16, 20, 18, 60, 26])


async def build_workbook(db) -> bytes:
    """Build a two-sheet XLSX report (Summary, Players) and return it as bytes."""
    wb = Workbook()
    wb.remove(wb.active)
    await _build_summary(db, wb)
    await _build_players(db, wb)
    await _build_withdrawals(db, wb)
    await _build_referrals(db, wb)
    await _build_admin_actions(db, wb)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()