from datetime import datetime
from sqlalchemy import CheckConstraint, Column, Date, Integer, String, Boolean, DateTime, ForeignKey, Text, UniqueConstraint
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
    journal_entries = relationship("GroupJournalEntry", back_populates="group", cascade="all, delete-orphan")
    lesson_progress = relationship("GroupLessonProgress", back_populates="group", cascade="all, delete-orphan")
    homeworks = relationship("GroupHomework", back_populates="group", cascade="all, delete-orphan")
    payment_entries = relationship("GroupPaymentEntry", back_populates="group", cascade="all, delete-orphan")
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
    journal_entries = relationship("GroupJournalEntry", back_populates="lesson", cascade="all, delete-orphan")
    progress_entries = relationship("GroupLessonProgress", back_populates="lesson", cascade="all, delete-orphan")
    homework = relationship("GroupHomework", back_populates="lesson", uselist=False, cascade="all, delete-orphan")
    vocabularies = relationship("VocabularySet", back_populates="lesson", cascade="all, delete-orphan")


class GroupMaterial(Base):
    __tablename__ = "group_materials"
    id = Column(Integer, primary_key=True)
    lesson_id = Column(Integer, ForeignKey("group_lessons.id"), nullable=False)
    title = Column(String, nullable=False)
    file_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    lesson = relationship("GroupLesson", back_populates="materials")


class GroupJournalEntry(Base):
    __tablename__ = "group_journal_entries"
    __table_args__ = (
        UniqueConstraint("group_id", "lesson_id", "student_id", name="uq_group_journal_entry"),
        CheckConstraint("grade IS NULL OR (grade >= 1 AND grade <= 5)", name="ck_group_journal_grade_range"),
    )

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("group_lessons.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    present = Column(Boolean, default=False, nullable=False)
    grade = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    group = relationship("Group", back_populates="journal_entries")
    lesson = relationship("GroupLesson", back_populates="journal_entries")
    student = relationship("User", foreign_keys=[student_id], back_populates="group_journal_entries")


class GroupLessonProgress(Base):
    __tablename__ = "group_lesson_progress"
    __table_args__ = (
        UniqueConstraint("group_id", "lesson_id", "student_id", name="uq_group_lesson_progress"),
    )

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("group_lessons.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    completed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    group = relationship("Group", back_populates="lesson_progress")
    lesson = relationship("GroupLesson", back_populates="progress_entries")
    student = relationship("User", foreign_keys=[student_id], back_populates="group_lesson_progress")


class GroupHomework(Base):
    __tablename__ = "group_homeworks"
    __table_args__ = (
        UniqueConstraint("group_id", "lesson_id", name="uq_group_homework_lesson"),
    )

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("group_lessons.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=True)
    description = Column(Text, nullable=False)
    material_url = Column(String, nullable=True)
    material_type = Column(String(50), nullable=True)
    material_filename = Column(String(255), nullable=True)
    deadline = Column(DateTime, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    group = relationship("Group", back_populates="homeworks")
    lesson = relationship("GroupLesson", back_populates="homework")
    created_by = relationship("User", foreign_keys=[created_by_id], back_populates="created_group_homeworks")
    submissions = relationship("GroupHomeworkSubmission", back_populates="homework", cascade="all, delete-orphan")


class GroupHomeworkSubmission(Base):
    __tablename__ = "group_homework_submissions"
    __table_args__ = (
        UniqueConstraint("homework_id", "student_id", name="uq_group_homework_submission_student"),
    )

    id = Column(Integer, primary_key=True)
    homework_id = Column(Integer, ForeignKey("group_homeworks.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    file_url = Column(String, nullable=True)
    file_type = Column(String(50), nullable=True)
    filename = Column(String(255), nullable=True)
    comment = Column(Text, nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    homework = relationship("GroupHomework", back_populates="submissions")
    student = relationship("User", foreign_keys=[student_id], back_populates="group_homework_submissions")


class GroupPaymentEntry(Base):
    __tablename__ = "group_payment_entries"
    __table_args__ = (
        UniqueConstraint("group_id", "student_id", "month", name="uq_group_payment_entry"),
    )

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    month = Column(Date, nullable=False)
    is_paid = Column(Boolean, default=False, nullable=False)
    paid_at = Column(DateTime, nullable=True)
    marked_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    group = relationship("Group", back_populates="payment_entries")
    student = relationship("User", foreign_keys=[student_id], back_populates="group_payment_entries")
    marked_by = relationship("User", foreign_keys=[marked_by_id], back_populates="marked_group_payments")
