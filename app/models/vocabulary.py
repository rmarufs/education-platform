"""
Модели для функционала «Словарь» в уроках группы.

VocabularySet      — набор слов, привязан к уроку группы
VocabularyItem     — одно слово с правильными ответами
VocabularyAttempt  — попытка студента пройти словарь (итоговая запись)
VocabularyAttemptAnswer — ответ студента на конкретное слово
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean,
    ForeignKey, DateTime,
)
from sqlalchemy.orm import relationship
from app.database import Base


class VocabularySet(Base):
    """Набор слов, привязанный к уроку группы."""
    __tablename__ = "vocabulary_sets"

    id = Column(Integer, primary_key=True, index=True)
    lesson_id = Column(Integer, ForeignKey("group_lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    allow_retake = Column(Boolean, default=False, nullable=False)  # повторное прохождение
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    lesson = relationship("GroupLesson", back_populates="vocabularies")
    items = relationship(
        "VocabularyItem",
        back_populates="vocab_set",
        order_by="VocabularyItem.position",
        cascade="all, delete-orphan",
    )
    attempts = relationship(
        "VocabularyAttempt",
        back_populates="vocab_set",
        cascade="all, delete-orphan",
    )

    @property
    def item_count(self):
        return len(self.items)


class VocabularyItem(Base):
    """Одно слово / термин с допустимыми ответами."""
    __tablename__ = "vocabulary_items"

    id = Column(Integer, primary_key=True, index=True)
    vocab_set_id = Column(Integer, ForeignKey("vocabulary_sets.id", ondelete="CASCADE"), nullable=False, index=True)
    position = Column(Integer, default=0, nullable=False)

    # Слово / термин, который видит студент
    prompt_word = Column(String(512), nullable=False)

    # Допустимые ответы — хранятся через разделитель «|»
    # accepted_answers — общий список (используется если нет языкового)
    accepted_answers = Column(Text, nullable=True)
    # Языковые варианты (опционально)
    accepted_answers_ru = Column(Text, nullable=True)
    accepted_answers_tj = Column(Text, nullable=True)

    vocab_set = relationship("VocabularySet", back_populates="items")
    answer_records = relationship(
        "VocabularyAttemptAnswer",
        back_populates="item",
        cascade="all, delete-orphan",
    )

    def get_accepted_answers(self, lang: str = "ru") -> list[str]:
        """
        Вернуть список допустимых ответов для заданного языка.
        Если языковой вариант пустой — использует общий список.
        """
        lang_field = self.accepted_answers_ru if lang == "ru" else self.accepted_answers_tj
        source = lang_field or self.accepted_answers or ""
        return [a.strip() for a in source.split("|") if a.strip()]


class VocabularyAttempt(Base):
    """Итоговая попытка студента пройти словарь."""
    __tablename__ = "vocabulary_attempts"

    id = Column(Integer, primary_key=True, index=True)
    vocab_set_id = Column(Integer, ForeignKey("vocabulary_sets.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    score = Column(Integer, default=0, nullable=False)        # кол-во правильных ответов
    total = Column(Integer, default=0, nullable=False)        # всего слов
    lang_used = Column(String(10), default="ru", nullable=False)  # язык при прохождении
    completed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    vocab_set = relationship("VocabularySet", back_populates="attempts")
    student = relationship("User")
    answers = relationship(
        "VocabularyAttemptAnswer",
        back_populates="attempt",
        cascade="all, delete-orphan",
    )

    @property
    def percentage(self) -> int:
        if not self.total:
            return 0
        return round(self.score / self.total * 100)


class VocabularyAttemptAnswer(Base):
    """Ответ студента на конкретное слово в рамках одной попытки."""
    __tablename__ = "vocabulary_attempt_answers"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("vocabulary_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("vocabulary_items.id", ondelete="CASCADE"), nullable=False)
    student_answer = Column(Text, nullable=True)
    is_correct = Column(Boolean, default=False, nullable=False)

    attempt = relationship("VocabularyAttempt", back_populates="answers")
    item = relationship("VocabularyItem", back_populates="answer_records")
