# Модель модуля курса
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Module(Base):
    __tablename__ = "modules"

    id          = Column(Integer, primary_key=True, index=True)
    course_id   = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    title       = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    order_index = Column(Integer, default=0, nullable=False)

    course  = relationship("Course", back_populates="modules")
    lessons = relationship("Lesson", back_populates="module",
                           order_by="Lesson.order_index",
                           cascade="all, delete-orphan")
