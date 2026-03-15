# Модель рейтинга и отзыва на курс
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        # Один студент — один отзыв на курс
        UniqueConstraint("course_id", "student_id", name="uq_course_student_review"),
    )

    id         = Column(Integer, primary_key=True, index=True)
    course_id  = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rating     = Column(Integer, nullable=False)    # 1–5
    text       = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("User")
