"""Tables for the folded-in features: Arcade (StoryVibe), The Button
(ButtonMania) and timed Drops (Token-Giver)."""
from sqlalchemy import Column, Integer, String, DateTime, BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


class ArcadeResult(Base):
    __tablename__ = "arcade_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    game = Column(String, nullable=False)            # "wheel" | "flip"
    stake = Column(Integer, default=0, nullable=False)
    payout = Column(Integer, default=0, nullable=False)
    outcome = Column(String, default="", nullable=False)
    day = Column(String, index=True, nullable=False)  # UTC YYYY-MM-DD
    created_at = Column(DateTime, default=func.now())


class ButtonState(Base):
    __tablename__ = "button_state"

    id = Column(Integer, primary_key=True)           # always 1
    total_presses = Column(BigInteger, default=0, nullable=False)


class ButtonUser(Base):
    __tablename__ = "button_users"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    presses = Column(BigInteger, default=0, nullable=False)
    last_press_at = Column(DateTime, nullable=True)
    claimed_milestone = Column(Integer, default=0, nullable=False)


class DropClaim(Base):
    __tablename__ = "drop_claims"
    __table_args__ = (UniqueConstraint("drop_key", "user_id", name="uq_drop_user"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    drop_key = Column(String, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=func.now())


class AdminSetting(Base):
    """Key/value store for the admin panel (GarageInc-style toggles)."""
    __tablename__ = "admin_settings"

    key = Column(String, primary_key=True)
    value = Column(String, default="", nullable=False)


class AdminAction(Base):
    """Audit log of admin panel actions."""
    __tablename__ = "admin_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(BigInteger, nullable=False)
    action = Column(String, nullable=False)
    target = Column(String, default="", nullable=False)
    detail = Column(String, default="", nullable=False)
    created_at = Column(DateTime, default=func.now())


class ArcadeDaily(Base):
    """Free-spin slots per user per day — claimed atomically via upsert so
    parallel spins can't all read 'spins left' and play free."""
    __tablename__ = "arcade_daily"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    day = Column(String, primary_key=True)  # UTC YYYY-MM-DD
    spins = Column(Integer, default=0, nullable=False)


class DropCounter(Base):
    """Authoritative per-drop claim counter (the pool cap is enforced by a
    guarded upsert, not by counting rows another request may not see yet)."""
    __tablename__ = "drop_counters"

    drop_key = Column(String, primary_key=True)
    claimed = Column(Integer, default=0, nullable=False)
