# Модель прогресса студента
from datetime import datetime
from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class Progress(Base):
    __tablename__ = "progress"
    __table_args__ = (
        # Один студент — один прогресс на урок
        UniqueConstraint("student_id", "lesson_id", name="uq_student_lesson"),
    )

    id           = Column(Integer, primary_key=True, index=True)
    student_id   = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    lesson_id    = Column(Integer, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    completed    = Column(Boolean, default=False, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    lesson  = relationship("Lesson", back_populates="progress")
