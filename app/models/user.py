# Модель пользователя
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, Boolean
from app.database import Base
import enum


class UserRole(str, enum.Enum):
    student = "student"
    teacher = "teacher"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.student, nullable=False)
    level = Column(String(50), nullable=True)
    assessment_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
