# Модель организации
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    logo_url = Column(String, nullable=True)
    website = Column(String, nullable=True)
    phone = Column(String(50), nullable=True)
    status = Column(String(20), default="pending")   # pending, approved, rejected
    is_open = Column(Boolean, default=True)  # True = открытый, False = закрытый
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="organization")
    teachers = relationship("OrganizationTeacher", back_populates="organization")
    students = relationship("OrganizationStudent", back_populates="organization")
    groups = relationship("Group", back_populates="organization", cascade="all, delete-orphan")
    announcements = relationship("OrganizationAnnouncement", back_populates="organization", cascade="all, delete-orphan")


class OrganizationTeacher(Base):
    __tablename__ = "organization_teachers"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"))
    teacher_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="pending")  # pending, accepted, rejected
    was_accepted_notification = Column(Boolean, default=False, nullable=False)
    cover_letter = Column(Text, nullable=True)   # сопроводительное письмо от преподавателя
    attachment = Column(String(500), nullable=True)  # путь к прикреплённому файлу
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="teachers")
    teacher = relationship("User", back_populates="employer_organizations")


class OrganizationStudent(Base):
    __tablename__ = "organization_students"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"))
    student_id = Column(Integer, ForeignKey("users.id"))
    # Статусы: 
    # pending - ожидает решения, 
    # accepted - участник, 
    # rejected - отклонен админом, 
    # left - ушел сам, 
    # removed - исключен админом (с уведомлением)
    status = Column(String(20), default="pending")
    was_removed_notification = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)     # Дата самого первого взаимодействия
    last_joined_at = Column(DateTime, nullable=True)           # Дата последнего одобренного вступления
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('student_id', 'organization_id', name='uq_student_org'),
    )

    # Relationships
    organization = relationship("Organization", back_populates="students")
    student = relationship("User", back_populates="student_organizations")


class OrganizationAnnouncement(Base):
    __tablename__ = "organization_announcements"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    audience = Column(String(20), nullable=False, default="all")  # teachers, students, all
    is_active = Column(Boolean, default=True, nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_org_announcements_org_active_created", "organization_id", "is_active", "created_at"),
        Index("ix_org_announcements_audience_expires", "audience", "expires_at"),
    )

    organization = relationship("Organization", back_populates="announcements")
    created_by = relationship("User", foreign_keys=[created_by_id])
    dismissals = relationship("OrganizationAnnouncementDismissal", back_populates="announcement", cascade="all, delete-orphan")


class OrganizationAnnouncementDismissal(Base):
    __tablename__ = "organization_announcement_dismissals"

    id = Column(Integer, primary_key=True)
    announcement_id = Column(Integer, ForeignKey("organization_announcements.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    dismissed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("announcement_id", "user_id", name="uq_announcement_user_dismissal"),
        Index("ix_org_announcement_dismissals_user", "user_id"),
    )

    announcement = relationship("OrganizationAnnouncement", back_populates="dismissals")
    user = relationship("User", foreign_keys=[user_id])
