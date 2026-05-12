from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    avatar_url = Column(String, nullable=True)
    quiz_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="groups")
    teacher = relationship("User", foreign_keys=[teacher_id])
    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
    modules = relationship(
        "GroupModule",
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="GroupModule.order_index",
    )
    lessons = relationship("GroupLesson", back_populates="group", cascade="all, delete-orphan", order_by="GroupLesson.order")


class GroupModule(Base):
    __tablename__ = "group_modules"
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False)
    order_index = Column(Integer, default=0, nullable=False)
    quiz_url = Column(String(500), nullable=True)

    group = relationship("Group", back_populates="modules")
    lessons = relationship(
        "GroupLesson",
        back_populates="group_module",
        order_by="GroupLesson.order",
    )


class GroupMember(Base):
    __tablename__ = "group_members"
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    grade = Column(Integer, nullable=True)   # класс 1-11
    is_paid = Column(Boolean, default=False)
    joined_at = Column(DateTime, default=datetime.utcnow)

    group = relationship("Group", back_populates="members")
    student = relationship("User", foreign_keys=[student_id])


class GroupLesson(Base):
    __tablename__ = "group_lessons"
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    group_module_id = Column(Integer, ForeignKey("group_modules.id", ondelete="SET NULL"), nullable=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    video_url = Column(String, nullable=True)
    cover_url = Column(String, nullable=True)
    quiz_url = Column(String(500), nullable=True)
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    group = relationship("Group", back_populates="lessons")
    group_module = relationship("GroupModule", back_populates="lessons")
    materials = relationship("GroupMaterial", back_populates="lesson", cascade="all, delete-orphan")


class GroupMaterial(Base):
    __tablename__ = "group_materials"
    id = Column(Integer, primary_key=True)
    lesson_id = Column(Integer, ForeignKey("group_lessons.id"), nullable=False)
    title = Column(String, nullable=False)
    file_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    lesson = relationship("GroupLesson", back_populates="materials")
