# Модель урока
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Lesson(Base):
    __tablename__ = "lessons"

    id          = Column(Integer, primary_key=True, index=True)
    module_id   = Column(Integer, ForeignKey("modules.id", ondelete="CASCADE"), nullable=False)
    title       = Column(String(200), nullable=False)
    video_url   = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    order_index = Column(Integer, default=0, nullable=False)

    module    = relationship("Module", back_populates="lessons")
    materials = relationship("Material", back_populates="lesson",
                             cascade="all, delete-orphan")
    quiz      = relationship("Quiz", back_populates="lesson",
                             uselist=False, cascade="all, delete-orphan")
    comments  = relationship("Comment", back_populates="lesson",
                             cascade="all, delete-orphan")
    progress  = relationship("Progress", back_populates="lesson",
                             cascade="all, delete-orphan")
