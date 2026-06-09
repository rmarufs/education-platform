from datetime import datetime
from sqlalchemy import CheckConstraint, Column, Date, Integer, String, Boolean, DateTime, ForeignKey, ForeignKeyConstraint, Text, UniqueConstraint, Index, text as sa_text
from sqlalchemy.orm import relationship
from app.database import Base


class Group(Base):
    __tablename__ = "groups"
    __table_args__ = (
        Index("ix_groups_org_id_created_at", "organization_id", "created_at"),
        Index("ix_groups_teacher_id_active_created_at", "teacher_id", "is_active", "created_at"),
    )

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
    __table_args__ = (
        UniqueConstraint("id", "group_id", name="uq_group_modules_id_group_id"),
        Index("ix_group_modules_group_id", "group_id"),
        Index("ix_group_modules_id", "id"),
    )

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
        primaryjoin="GroupModule.id == GroupLesson.group_module_id",
        foreign_keys="GroupLesson.group_module_id",
    )


class GroupMember(Base):
    __tablename__ = "group_members"
    __table_args__ = (
        UniqueConstraint("group_id", "student_id", name="uq_group_member_student"),
        CheckConstraint("payment_day IS NULL OR (payment_day >= 1 AND payment_day <= 31)", name="ck_group_members_payment_day_range"),
        Index("ix_group_members_student_id", "student_id"),
    )

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    grade = Column(Integer, nullable=True)   # класс 1-11
    is_paid = Column(Boolean, default=False)
    payment_day = Column(Integer, default=1, nullable=True)
    paid_until = Column(Date, nullable=True)
    last_paid_at = Column(DateTime, nullable=True)
    joined_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default="active", server_default=sa_text("'active'"), nullable=False)
    removed_at = Column(DateTime, nullable=True)
    left_at = Column(DateTime, nullable=True)
    removed_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, nullable=True)
    last_joined_at = Column(DateTime, nullable=True)

    group = relationship("Group", back_populates="members")
    student = relationship("User", foreign_keys=[student_id])


class GroupLesson(Base):
    __tablename__ = "group_lessons"
    __table_args__ = (
        UniqueConstraint("id", "group_id", name="uq_group_lessons_id_group_id"),
        ForeignKeyConstraint(
            ["group_module_id", "group_id"],
            ["group_modules.id", "group_modules.group_id"],
            name="fk_group_lessons_module_group",
        ),
        Index("ix_group_lessons_group_id_order", "group_id", "order"),
        Index("ix_group_lessons_group_module_id", "group_module_id"),
    )

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
    group_module = relationship(
        "GroupModule",
        back_populates="lessons",
        primaryjoin="GroupModule.id == GroupLesson.group_module_id",
        foreign_keys=[group_module_id],
    )
    materials = relationship("GroupMaterial", back_populates="lesson", cascade="all, delete-orphan")
    journal_entries = relationship(
        "GroupJournalEntry",
        back_populates="lesson",
        cascade="all, delete-orphan",
        primaryjoin="GroupLesson.id == GroupJournalEntry.lesson_id",
        foreign_keys="GroupJournalEntry.lesson_id",
    )
    progress_entries = relationship(
        "GroupLessonProgress",
        back_populates="lesson",
        cascade="all, delete-orphan",
        primaryjoin="GroupLesson.id == GroupLessonProgress.lesson_id",
        foreign_keys="GroupLessonProgress.lesson_id",
    )
    homework = relationship(
        "GroupHomework",
        back_populates="lesson",
        uselist=False,
        cascade="all, delete-orphan",
        primaryjoin="GroupLesson.id == GroupHomework.lesson_id",
        foreign_keys="GroupHomework.lesson_id",
    )
    vocabularies = relationship("VocabularySet", back_populates="lesson", cascade="all, delete-orphan")


class GroupMaterial(Base):
    __tablename__ = "group_materials"
    __table_args__ = (
        Index("ix_group_materials_lesson_id", "lesson_id"),
    )

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
        ForeignKeyConstraint(
            ["lesson_id", "group_id"],
            ["group_lessons.id", "group_lessons.group_id"],
            name="fk_group_journal_lesson_group",
            ondelete="CASCADE",
        ),
        CheckConstraint("grade IS NULL OR (grade >= 1 AND grade <= 5)", name="ck_group_journal_grade_range"),
        CheckConstraint("score_percent IS NULL OR score_percent BETWEEN 0 AND 100", name="ck_group_journal_score_percent_range"),
        Index("ix_group_journal_entries_group_id", "group_id"),
        Index("ix_group_journal_entries_lesson_id", "lesson_id"),
        Index("ix_group_journal_entries_student_id", "student_id"),
    )

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("group_lessons.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    present = Column(Boolean, default=False, nullable=False)
    grade = Column(Integer, nullable=True)
    score_percent = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    group = relationship("Group", back_populates="journal_entries")
    lesson = relationship(
        "GroupLesson",
        back_populates="journal_entries",
        primaryjoin="GroupLesson.id == GroupJournalEntry.lesson_id",
        foreign_keys=[lesson_id],
    )
    student = relationship("User", foreign_keys=[student_id], back_populates="group_journal_entries")


class GroupLessonProgress(Base):
    __tablename__ = "group_lesson_progress"
    __table_args__ = (
        UniqueConstraint("group_id", "lesson_id", "student_id", name="uq_group_lesson_progress"),
        ForeignKeyConstraint(
            ["lesson_id", "group_id"],
            ["group_lessons.id", "group_lessons.group_id"],
            name="fk_group_lesson_progress_lesson_group",
            ondelete="CASCADE",
        ),
        Index("ix_group_lesson_progress_group_id", "group_id"),
        Index("ix_group_lesson_progress_lesson_id", "lesson_id"),
        Index("ix_group_lesson_progress_student_id", "student_id"),
    )

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("group_lessons.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    completed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    group = relationship("Group", back_populates="lesson_progress")
    lesson = relationship(
        "GroupLesson",
        back_populates="progress_entries",
        primaryjoin="GroupLesson.id == GroupLessonProgress.lesson_id",
        foreign_keys=[lesson_id],
    )
    student = relationship("User", foreign_keys=[student_id], back_populates="group_lesson_progress")


class GroupHomework(Base):
    __tablename__ = "group_homeworks"
    __table_args__ = (
        UniqueConstraint("group_id", "lesson_id", name="uq_group_homework_lesson"),
        ForeignKeyConstraint(
            ["lesson_id", "group_id"],
            ["group_lessons.id", "group_lessons.group_id"],
            name="fk_group_homeworks_lesson_group",
            ondelete="CASCADE",
        ),
        Index("ix_group_homeworks_created_by_id", "created_by_id"),
        Index("ix_group_homeworks_group_id", "group_id"),
        Index("ix_group_homeworks_lesson_id", "lesson_id"),
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
    lesson = relationship(
        "GroupLesson",
        back_populates="homework",
        primaryjoin="GroupLesson.id == GroupHomework.lesson_id",
        foreign_keys=[lesson_id],
    )
    created_by = relationship("User", foreign_keys=[created_by_id], back_populates="created_group_homeworks")
    submissions = relationship("GroupHomeworkSubmission", back_populates="homework", cascade="all, delete-orphan")


class GroupHomeworkSubmission(Base):
    __tablename__ = "group_homework_submissions"
    __table_args__ = (
        UniqueConstraint("homework_id", "student_id", name="uq_group_homework_submission_student"),
        Index("ix_group_homework_submissions_homework_id", "homework_id"),
        Index("ix_group_homework_submissions_reviewed_by_id", "reviewed_by_id"),
        Index("ix_group_homework_submissions_student_id", "student_id"),
    )

    id = Column(Integer, primary_key=True)
    homework_id = Column(Integer, ForeignKey("group_homeworks.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    file_url = Column(String, nullable=True)
    file_type = Column(String(50), nullable=True)
    filename = Column(String(255), nullable=True)
    comment = Column(Text, nullable=True)
    teacher_comment = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    homework_reply_read_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    homework = relationship("GroupHomework", back_populates="submissions")
    student = relationship("User", foreign_keys=[student_id], back_populates="group_homework_submissions")
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id], back_populates="reviewed_group_homework_submissions")


class GroupHomeworkNotification(Base):
    __tablename__ = "group_homework_notifications"
    __table_args__ = (
        UniqueConstraint("homework_id", "student_id", "notification_type", name="uq_group_homework_notification_student"),
        Index("ix_group_homework_notifications_student_read", "student_id", "read_at"),
    )

    id = Column(Integer, primary_key=True)
    homework_id = Column(Integer, ForeignKey("group_homeworks.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    notification_type = Column(String(50), default="new_homework", nullable=False)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    homework = relationship("GroupHomework")
    student = relationship("User", foreign_keys=[student_id])


class GroupPaymentEntry(Base):
    __tablename__ = "group_payment_entries"
    __table_args__ = (
        UniqueConstraint("group_id", "student_id", "month", name="uq_group_payment_entry"),
        CheckConstraint("payment_day IS NULL OR (payment_day >= 1 AND payment_day <= 31)", name="ck_group_payment_entries_payment_day_range"),
        Index("ix_group_payment_entries_group_id", "group_id"),
        Index("ix_group_payment_entries_month", "month"),
        Index("ix_group_payment_entries_student_id", "student_id"),
    )

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    month = Column(Date, nullable=False)
    is_paid = Column(Boolean, default=False, nullable=False)
    paid_at = Column(DateTime, nullable=True)
    marked_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    payment_day = Column(Integer, nullable=True)
    paid_until = Column(Date, nullable=True)
    action = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    group = relationship("Group", back_populates="payment_entries")
    student = relationship("User", foreign_keys=[student_id], back_populates="group_payment_entries")
    marked_by = relationship("User", foreign_keys=[marked_by_id], back_populates="marked_group_payments")


class GroupLessonChatMessage(Base):
    __tablename__ = "group_lesson_chat_messages"
    __table_args__ = (
        Index("ix_group_lesson_chat_group_lesson", "group_id", "lesson_id"),
        Index("ix_group_lesson_chat_lesson_created", "lesson_id", "created_at"),
        Index("ix_group_lesson_chat_messages_recipient_id", "recipient_id"),
        Index("ix_group_lesson_chat_messages_user_id", "user_id"),
        Index("ix_group_lesson_chat_scope_lesson", "lesson_id", "message_scope", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("group_lessons.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)
    recipient_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    message_scope = Column(String(20), server_default=sa_text("'public'"), nullable=False)

    group = relationship("Group")
    lesson = relationship("GroupLesson")
    user = relationship("User", foreign_keys=[user_id])
    recipient = relationship("User", foreign_keys=[recipient_id])


class GroupLessonSession(Base):
    __tablename__ = "group_lesson_sessions"
    __table_args__ = (
        UniqueConstraint("group_id", "lesson_id", name="uq_group_lesson_session"),
        Index("ix_group_lesson_sessions_group_status", "group_id", "status"),
    )

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("group_lessons.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), server_default=sa_text("'not_started'"), nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    started_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    completed_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    group = relationship("Group")
    lesson = relationship("GroupLesson")
    started_by = relationship("User", foreign_keys=[started_by_id])
    completed_by = relationship("User", foreign_keys=[completed_by_id])
