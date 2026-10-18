from datetime import datetime, date
from sqlalchemy import Column, Integer, String, BigInteger, Boolean, DateTime, Date, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import relationship
from app.database import Base


class MiningSession(Base):
    __tablename__ = "mining_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.now, nullable=False)
    ends_at = Column(DateTime, nullable=False)
    hourly_rate = Column(Integer, nullable=False)  # CSM per hour, locked at session start
    claimed = Column(Boolean, default=False, nullable=False)
    claimed_at = Column(DateTime, nullable=True)

    user = relationship("User")


class DailyClaim(Base):
    """One row per user per calendar day a daily bonus was claimed — drives streaks."""
    __tablename__ = "daily_claims"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    claim_date = Column(Date, default=date.today, nullable=False)
    claimed_at = Column(DateTime, default=datetime.now, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "claim_date", name="uq_daily_claim_user_date"),
    )


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, unique=True, nullable=False, index=True)
    reward = Column(Integer, nullable=False)  # CSM
    max_uses = Column(Integer, nullable=True)  # None = unlimited
    uses = Column(Integer, default=0, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    active = Column(Boolean, default=True, nullable=False)

    redemptions = relationship("PromoRedemption", back_populates="promo_code")


class PromoRedemption(Base):
    __tablename__ = "promo_redemptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    code_id = Column(Integer, ForeignKey("promo_codes.id"), nullable=False)
    redeemed_at = Column(DateTime, default=datetime.now, nullable=False)

    promo_code = relationship("PromoCode", back_populates="redemptions")

    __table_args__ = (
        UniqueConstraint("user_id", "code_id", name="uq_promo_user_code"),
    )


class WithdrawalRequest(Base):
    __tablename__ = "withdrawal_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)  # CSM debited into escrow
    address = Column(String, nullable=False)  # TON address
    status = Column(String, default="pending", nullable=False)  # pending/approved/rejected/paid
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    reviewed_by = Column(BigInteger, nullable=True)  # admin telegram_id
    reviewed_at = Column(DateTime, nullable=True)
    tx_hash = Column(String, nullable=True)  # payout transaction (set when marked paid)
    paid_at = Column(DateTime, nullable=True)

    user = relationship("User")


class ReferralEarning(Base):
    """Ledger of every referral payout — drives the Crew screen's per-friend earnings."""
    __tablename__ = "referral_earnings_ledger"
    __table_args__ = (
        Index(
            "uq_referral_oneshot",
            "referrer_id",
            "from_user_id",
            "kind",
            unique=True,
            sqlite_where=text("kind IN ('qual', 'milestone')"),
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)  # CSM paid to the referrer
    tier = Column(Integer, nullable=False)  # 1 = direct, 2 = friend-of-friend
    kind = Column(String, nullable=False)  # yield / qual / milestone / og
    created_at = Column(DateTime, default=datetime.now, nullable=False)


class BotStart(Base):
    """One row per Telegram user who pressed /start in the game bot —
    lets tasks verify 'open the bot' actions server-side."""
    __tablename__ = "bot_starts"

    telegram_id = Column(BigInteger, primary_key=True)
    started_at = Column(DateTime, default=datetime.now, nullable=False)
