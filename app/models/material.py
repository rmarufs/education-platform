# Модель файлового материала урока
from sqlalchemy import Column, Integer, String, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database import Base


class Material(Base):
    __tablename__ = "materials"
    __table_args__ = (
        Index("ix_materials_course_id", "course_id"),
    )

    id        = Column(Integer, primary_key=True, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=True)
    title     = Column(String(200), nullable=True)
    file_url  = Column(String(500), nullable=False)
    file_type = Column(String(20), nullable=True)  # pdf, ppt, doc, etc.

    lesson = relationship("Lesson", back_populates="materials")
    course = relationship("Course", back_populates="materials")
