# Модель организации
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
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
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="organization")
    teachers = relationship("OrganizationTeacher", back_populates="organization")
    students = relationship("OrganizationStudent", back_populates="organization")


class OrganizationTeacher(Base):
    __tablename__ = "organization_teachers"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"))
    teacher_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="pending")  # pending, accepted, rejected
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
    status = Column(String(20), default="pending")  # pending, accepted, rejected
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="students")
    student = relationship("User", back_populates="student_organizations")
