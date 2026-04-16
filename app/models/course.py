# Модель курса
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from app.database import Base


class Course(Base):
    __tablename__ = "courses"

    id          = Column(Integer, primary_key=True, index=True)
    title       = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    image       = Column(String(500), nullable=True)
    level       = Column(String(50), default="Beginner")
    teacher_id  = Column(Integer, ForeignKey("users.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    rating      = Column(Float, default=0.0)          # средний рейтинг
    quiz_url    = Column(String(500), nullable=True)  # ссылка на Google Forms для теста курса
    created_at  = Column(DateTime, default=datetime.utcnow)

    teacher  = relationship("User", backref="courses")
    category = relationship("Category")
    modules  = relationship("Module", back_populates="course",
                            order_by="Module.order_index",
                            cascade="all, delete-orphan")
    reviews  = relationship("Review", cascade="all, delete-orphan",
                            foreign_keys="Review.course_id")
    materials = relationship("Material", back_populates="course",
                             cascade="all, delete-orphan")
    quiz = relationship("Quiz", back_populates="course",
                        uselist=False, cascade="all, delete-orphan")
