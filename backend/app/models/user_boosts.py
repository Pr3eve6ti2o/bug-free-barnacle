from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class UserBoost(Base):
    __tablename__ = "user_boosts"
    __table_args__ = (UniqueConstraint("user_id", "boost_id", name="ux_user_boost"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    boost_id = Column(Integer, ForeignKey("boosts.id"))
    level = Column(Integer, default=0)  # Текущий уровень буста у пользователя

    user = relationship("User", back_populates="boosts")
    boost = relationship("Boost", back_populates="users")
