# Модели квиза: Quiz → Question → Answer
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class Quiz(Base):
    __tablename__ = "quizzes"

    id        = Column(Integer, primary_key=True, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=True)
    module_id = Column(Integer, ForeignKey("modules.id", ondelete="CASCADE"), nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=True)
    title     = Column(String(200), nullable=False)
    save_results = Column(Boolean, default=True, nullable=False)

    lesson    = relationship("Lesson", back_populates="quiz")
    module    = relationship("Module", back_populates="quiz")
    course    = relationship("Course", back_populates="quiz")
    questions = relationship("Question", back_populates="quiz",
                             order_by="Question.id",
                             cascade="all, delete-orphan")
    attempts  = relationship("QuizAttempt", back_populates="quiz",
                             cascade="all, delete-orphan")
    results   = relationship("QuizResult", back_populates="quiz",
                             cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id             = Column(Integer, primary_key=True, index=True)
    quiz_id        = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    question_text  = Column(String(500), nullable=False)
    question_type  = Column(String(20), default="single")  # single | multiple | open
    correct_text   = Column(String(500), nullable=True)

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


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"
    __table_args__ = (
        UniqueConstraint("quiz_id", "student_id", name="uq_quiz_attempt_student"),
    )

    id          = Column(Integer, primary_key=True, index=True)
    quiz_id     = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    student_id  = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    correct     = Column(Integer, default=0, nullable=False)
    total       = Column(Integer, default=0, nullable=False)
    score       = Column(Integer, default=0, nullable=False)
    completed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    quiz = relationship("Quiz", back_populates="attempts")


class QuizResult(Base):
    __tablename__ = "quiz_results"

    id         = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    quiz_id    = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    score      = Column(Integer, default=0, nullable=False)
    total      = Column(Integer, default=0, nullable=False)
    percentage = Column(Integer, default=0, nullable=False)
    passed     = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    quiz = relationship("Quiz", back_populates="results")
    student = relationship("User")
