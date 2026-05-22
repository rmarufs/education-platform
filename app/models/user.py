# Модель пользователя
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, Boolean
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class UserRole(str, enum.Enum):
    student = "student"
    teacher = "teacher"
    teacher_pending = "teacher_pending"
    admin = "admin"
    organization = "organization"
    guest = "guest"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.student, nullable=False)
    level = Column(String(50), nullable=True)
    assessment_completed = Column(Boolean, default=False)
    documents = Column(String(500), nullable=True)   # путь к PDF-файлу преподавателя
    bio = Column(Text, nullable=True)                 # рассказ о себе (для преподавателей)
    avatar_url = Column(String, nullable=True)         # URL фото профиля
    is_active = Column(Boolean, default=True)         # для блокировки пользователей
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
