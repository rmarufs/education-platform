# Модели квиза: Quiz → Question → Answer
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Quiz(Base):
    __tablename__ = "quizzes"

    id        = Column(Integer, primary_key=True, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    title     = Column(String(200), nullable=False)

    lesson    = relationship("Lesson", back_populates="quiz")
    questions = relationship("Question", back_populates="quiz",
                             order_by="Question.id",
                             cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id            = Column(Integer, primary_key=True, index=True)
    quiz_id       = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    question_text = Column(String(500), nullable=False)
    question_type = Column(String(20), default="single")  # single | multiple

    quiz    = relationship("Quiz", back_populates="questions")
    answers = relationship("Answer", back_populates="question",
                           cascade="all, delete-orphan")


class Answer(Base):
    __tablename__ = "answers"

    id          = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    answer_text = Column(String(500), nullable=False)
    is_correct  = Column(Boolean, default=False, nullable=False)

    question = relationship("Question", back_populates="answers")
