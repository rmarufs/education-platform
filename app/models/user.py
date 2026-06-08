# Модель пользователя
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Date, Enum, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class UserRole(str, enum.Enum):
    student = "student"
    teacher = "teacher"
    teacher_pending = "teacher_pending"
    admin = "admin"
    organization = "organization"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.student, nullable=False)
    documents = Column(String(500), nullable=True)   # путь к PDF-файлу преподавателя
    bio = Column(Text, nullable=True)                 # рассказ о себе (для преподавателей)
    avatar_url = Column(String, nullable=True)         # URL фото профиля
    birth_date = Column(Date, nullable=True)
    phone_number = Column(String(32), nullable=True)
    parent_contact_name = Column(String(150), nullable=True)
    parent_contact_phone = Column(String(32), nullable=True)
    is_active = Column(Boolean, default=True)         # для блокировки пользователей
    gender = Column(String(10), nullable=True)        # пол пользователя (male/female)
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="user", uselist=False)
    employer_organizations = relationship("OrganizationTeacher", back_populates="teacher")
    student_organizations = relationship("OrganizationStudent", back_populates="student")
    group_journal_entries = relationship("GroupJournalEntry", back_populates="student")
    group_lesson_progress = relationship("GroupLessonProgress", back_populates="student")
    created_group_homeworks = relationship("GroupHomework", back_populates="created_by")
    group_homework_submissions = relationship("GroupHomeworkSubmission", foreign_keys="GroupHomeworkSubmission.student_id", back_populates="student")
    reviewed_group_homework_submissions = relationship("GroupHomeworkSubmission", foreign_keys="GroupHomeworkSubmission.reviewed_by_id", back_populates="reviewed_by")
    group_payment_entries = relationship("GroupPaymentEntry", foreign_keys="GroupPaymentEntry.student_id", back_populates="student")
    marked_group_payments = relationship("GroupPaymentEntry", foreign_keys="GroupPaymentEntry.marked_by_id", back_populates="marked_by")
    push_subscriptions = relationship("PushSubscription", back_populates="user", cascade="all, delete-orphan")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")

    @property
    def is_teacher(self) -> bool:
        return self.role.value == "teacher"

    @property
    def is_student(self) -> bool:
        return self.role.value == "student"

    @property
    def is_admin(self) -> bool:
        return self.role.value == "admin"

    @property
    def is_org(self) -> bool:
        return self.role.value == "organization"


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    used_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    request_ip = Column(String(64), nullable=True)
    user_agent = Column(String(255), nullable=True)

    user = relationship("User", back_populates="password_reset_tokens")


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    endpoint = Column(String(500), nullable=False, unique=True)
    p256dh = Column(String(200), nullable=False)
    auth = Column(String(200), nullable=False)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="push_subscriptions")
