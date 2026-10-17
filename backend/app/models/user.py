from sqlalchemy import Column, Integer, String, Text, DateTime, BigInteger, Boolean, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    # Идентификаторы
    id = Column(Integer, primary_key=True, autoincrement=True)  # Внутренний ID для связей
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)  # ID из Telegram

    username = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=func.now())
    referred_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Поле для хранения адреса TON кошелька
    ton_wallet_address = Column(String, nullable=True)

    # Play-2-Earn поля
    lifetime_earned = Column(Integer, default=0, nullable=False)  # всего заработано, никогда не уменьшается
    lifetime_mined = Column(Integer, default=0, nullable=False)  # только доход от майнинга; ворота квалификации реферера (бонусы не считаются)
    referral_earnings = Column(Integer, default=0, nullable=False)  # заработано с рефералов (5%)
    referral_milestones_claimed = Column(String, default="", nullable=False)  # "5,25" — полученные майлстоуны
    streak_milestones_claimed = Column(String, default="", nullable=False)  # "7,30" — стрик-майлстоуны
    og_pass_expires_at = Column(DateTime, nullable=True)
    welcome_claimed = Column(Boolean, default=False, nullable=False)
    terms_accepted_version = Column(Integer, default=0, nullable=False)

    # Referral core v2 (ATF-style)
    pending_invite_bonus = Column(Integer, default=0, nullable=False)  # escrowed invitee bonus, paid on first mining claim
    qual_bonus_paid = Column(Boolean, default=False, nullable=False)  # inviter's qualification bonus paid for this user
    ref_milestone_paid = Column(Boolean, default=False, nullable=False)  # 10k-lifetime referral milestone paid
    banned = Column(Boolean, default=False, nullable=False)  # admin suspension (panel)
    ban_reason = Column(String, nullable=True)

    # Отношения
    game_state = relationship("GameState", back_populates="user", uselist=False)
    daily_game_state = relationship("DailyGameState", back_populates="user", uselist=False)
    boosts = relationship("UserBoost", back_populates="user")
    tasks = relationship("UserTask", back_populates="user")
    nfts = relationship("UserNFT", back_populates="user")
    referred_users = relationship(
        "User",
        backref=backref("referrer", remote_side=[id]),
        cascade="all, delete",
    )
    daily_bonus = relationship("UserDailyBonus", back_populates="user", uselist=False)


