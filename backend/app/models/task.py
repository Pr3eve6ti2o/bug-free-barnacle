from sqlalchemy import Column, Integer, String, Float, Enum, Boolean
from sqlalchemy.orm import relationship
from app.database import Base
from sqlalchemy import Enum as SQLEnum
import enum


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, index=True)
    type = Column(String, nullable=False)
    reward = Column(Integer, default=10)
    reward_type = Column(String, default="token")  # token | multiplier
    multiplier_pct = Column(Float, default=0)  # +% к скорости майнинга (для reward_type=multiplier)
    link_url = Column(String, nullable=True)  # внешняя ссылка для заданий-действий
    is_active = Column(Boolean, default=True, nullable=False)  # панель: скрыть задание без удаления
    condition_value = Column(Integer, nullable=False) 
    condition_type = Column(String, nullable=False)  

    users = relationship("UserTask", back_populates="task")

    def __repr__(self):
        return f"<Task(id={self.id}, reward={self.reward})>"
