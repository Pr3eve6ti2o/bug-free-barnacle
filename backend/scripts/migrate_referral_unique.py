"""One-off migration: one-shot referral payout uniqueness.

referral_earnings_ledger is an append-only audit trail: every payout writes a
row and nothing is ever updated or deleted, so the qual/milestone flag columns
on the user row are the only thing standing between a racing pair of requests
and a double payout. Two concurrent qualify paths can both read the flag as
unset and both insert — the ledger would then hold two 'qual' rows for the same
(referrer, from_user) pair, and the referrer gets paid twice for one signup.
This partial unique index backstops that flag logic at the storage layer, so the
second insert fails instead of silently double-crediting.

The index is PARTIAL on purpose. Only 'qual' and 'milestone' are meant to be
one-shot per pair. 'yield', 'og' and 'admin_grant' rows legitimately recur — the
same referrer earns yield over and over from the same downline user, og bonuses
can be re-granted, and admin grants are manual and repeatable — so a plain
UNIQUE(referrer_id, from_user_id, kind) would reject valid ledger rows.

Idempotent: the duplicate count is read-only (no rows are touched, ever — the
ledger is an audit trail) and the index is created with IF NOT EXISTS. If
duplicates for the covered kinds already exist, CREATE UNIQUE INDEX raises and
this script fails loudly by design rather than papering over the double payout;
resolve those rows by hand first.
"""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[2] / "demo.db"


def main() -> None:
    conn = sqlite3.connect(DB)
    try:
        # Report only. Deleting or rewriting ledger rows would destroy the
        # audit trail, so duplicates are surfaced and left for a human.
        dupes = conn.execute(
            "SELECT COUNT(*) FROM ("
            "  SELECT 1 FROM referral_earnings_ledger"
            "  WHERE kind IN ('qual', 'milestone')"
            "  GROUP BY referrer_id, from_user_id, kind"
            "  HAVING COUNT(*) > 1)"
        ).fetchone()[0]
        print(f"referral_earnings_ledger: {dupes} duplicate qual/milestone group(s)")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_referral_oneshot "
            "ON referral_earnings_ledger (referrer_id, from_user_id, kind) "
            "WHERE kind IN ('qual', 'milestone')"
        )
        conn.commit()
        print(f"referral_earnings_ledger: {dupes} duplicate group(s); uq_referral_oneshot present")
    finally:
        conn.close()


if __name__ == "__main__":
    main()