import re
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import DatabaseError
from app.models.vocabulary import VocabularyAttempt

def parse_words_bulk(text: str) -> list[dict]:
    """
    Парсит текстовый блок в список слов.
    Формат каждой строки: слово = ответ1; ответ2; ответ3
    Возвращает список словарей с ключами prompt_word и accepted_answers (через |).
    """
    items = []
    for i, line in enumerate(text.splitlines()):
        line = line.strip()
        if not line or "=" not in line:
            continue
        parts = line.split("=", 1)
        prompt = parts[0].strip()
        answers_raw = parts[1].strip()
        # Разделитель ответов — точка с запятой или запятая, нормализуем в |
        answers = [a.strip() for a in re.split(r"[;,]", answers_raw) if a.strip()]
        if not prompt or not answers:
            continue
        items.append({
            "prompt_word": prompt,
            "accepted_answers": "|".join(answers),
            "position": i,
        })
    return items


def is_vocabulary_anticheat_schema_mismatch(exc: DatabaseError) -> bool:
    anti_cheat_columns = (
        "anti_cheat_flags_count",
        "anti_cheat_teacher_visible",
        "anti_cheat_last_flag_at",
    )
    orig = getattr(exc, "orig", None)
    parts = [str(exc), exc.__class__.__name__]
    if orig:
        parts.extend([
            str(orig),
            orig.__class__.__name__,
            str(getattr(orig, "pgcode", "")),
            str(getattr(orig, "sqlstate", "")),
        ])
    message = " ".join(part for part in parts if part).lower()
    if not any(column in message for column in anti_cheat_columns):
        return False

    undefined_column_codes = {"42703"}
    if getattr(orig, "pgcode", None) in undefined_column_codes or getattr(orig, "sqlstate", None) in undefined_column_codes:
        return True

    missing_column_markers = (
        "undefinedcolumn",
        "undefined column",
        "no such column",
        "has no column",
        "no column named",
        "does not exist",
        "unknown column",
        "column not found",
    )
    return any(marker in message for marker in missing_column_markers)


def create_vocabulary_attempt_record(db: Session, vocab_id: int, student_id: int) -> int:
    new_attempt = VocabularyAttempt(
        vocab_set_id=vocab_id,
        student_id=student_id,
        is_completed=False,
    )
    db.add(new_attempt)
    try:
        db.commit()
        db.refresh(new_attempt)
        return new_attempt.id
    except DatabaseError as exc:
        db.rollback()
        if not is_vocabulary_anticheat_schema_mismatch(exc):
            raise

    attempt_id = db.execute(
        text(
            """
            INSERT INTO vocabulary_attempts
                (vocab_set_id, student_id, score, total, lang_used, is_completed, retake_allowed, completed_at)
            VALUES
                (:vocab_set_id, :student_id, 0, 0, 'ru', :is_completed, :retake_allowed, :completed_at)
            RETURNING id
            """
        ),
        {
            "vocab_set_id": vocab_id,
            "student_id": student_id,
            "is_completed": False,
            "retake_allowed": False,
            "completed_at": datetime.utcnow(),
        },
    ).scalar_one()
    db.commit()
    return attempt_id


from app.models.vocabulary import VocabularySet, VocabularyItem

def create_vocabulary_set_record(db: Session, lesson_id: int, title: str, description: str, words_bulk: str):
    vocab = VocabularySet(
        lesson_id=lesson_id,
        title=title.strip(),
        description=description.strip() or None,
    )
    db.add(vocab)
    db.flush()

    for word_data in parse_words_bulk(words_bulk):
        db.add(VocabularyItem(
            vocab_set_id=vocab.id,
            prompt_word=word_data["prompt_word"],
            accepted_answers=word_data["accepted_answers"],
            position=word_data["position"],
        ))

    db.commit()


def update_vocabulary_set_record(db: Session, vocab: VocabularySet, title: str, description: str, words_bulk: str):
    vocab.title = title.strip()
    vocab.description = description.strip() or None

    db.query(VocabularyItem).filter(VocabularyItem.vocab_set_id == vocab.id).delete()

    for word_data in parse_words_bulk(words_bulk):
        db.add(VocabularyItem(
            vocab_set_id=vocab.id,
            prompt_word=word_data["prompt_word"],
            accepted_answers=word_data["accepted_answers"],
            position=word_data["position"],
        ))

    db.commit()


def delete_vocabulary_set_record(db: Session, vocab: VocabularySet):
    db.query(VocabularyAttempt).filter(VocabularyAttempt.vocab_set_id == vocab.id).delete()
    db.query(VocabularyItem).filter(VocabularyItem.vocab_set_id == vocab.id).delete()
    db.delete(vocab)
    db.commit()

