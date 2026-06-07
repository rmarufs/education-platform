import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session, joinedload, load_only
from sqlalchemy.exc import DatabaseError, IntegrityError

from app.database import get_db
from app.ui import templates
from app.models.group import (
    Group, GroupMember, GroupModule, GroupLesson
)
from app.models.vocabulary import (
    VocabularySet, VocabularyItem, VocabularyAttempt, VocabularyAttemptAnswer
)
from app.models.user import User
from app.models.organization import Organization
from app.deps.auth import get_user as _get_user
from app.services.group_vocabulary_service import (
    parse_words_bulk, create_vocabulary_attempt_record, is_vocabulary_anticheat_schema_mismatch, create_vocabulary_set_record, update_vocabulary_set_record, delete_vocabulary_set_record
)

router = APIRouter()

def _require_login(request: Request, db: Session):
    user = _get_user(request, db)
    if not user:
        return None, RedirectResponse("/login", status_code=302)
    return user, None


def _can_manage_group_content(user: User, group: Group, db: Session) -> bool:
    if user.is_org:
        org = db.query(Organization).filter(Organization.user_id == user.id).first()
        return bool(org and group.organization_id == org.id)
    if user.is_teacher:
        return group.teacher_id == user.id
    return False


def _get_manageable_group(group_id: int, request: Request, db: Session) -> tuple[User, Group]:
    user = _get_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Необходима авторизация")

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    if not _can_manage_group_content(user, group, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    return user, group





@router.get("/{group_id:int}/lessons/{lesson_id:int}/vocabulary/create", response_class=HTMLResponse)
def vocab_create_page(
    group_id: int,
    lesson_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group or not _can_manage_group_content(user, group, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    lesson = db.query(GroupLesson).filter(
        GroupLesson.id == lesson_id,
        GroupLesson.group_id == group_id,
    ).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")

    return templates.TemplateResponse("groups/vocabulary_edit.html", {
        "request": request,
        "user": user,
        "group": group,
        "lesson": lesson,
        "vocab": None,
        "words_bulk": "",
        "can_preview_as_owner": True,
    })


@router.post("/{group_id:int}/lessons/{lesson_id:int}/vocabulary/create")
async def vocab_create(
    group_id: int,
    lesson_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    words_bulk: str = Form(""),
    db: Session = Depends(get_db),
):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group or not _can_manage_group_content(user, group, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    lesson = db.query(GroupLesson).filter(
        GroupLesson.id == lesson_id,
        GroupLesson.group_id == group_id,
    ).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")

    vocab = VocabularySet(
        lesson_id=lesson_id,
        title=title.strip(),
        description=description.strip() or None,
    )
    db.add(vocab)
    db.flush()  # получаем vocab.id

    for word_data in parse_words_bulk(words_bulk):
        db.add(VocabularyItem(
            vocab_set_id=vocab.id,
            prompt_word=word_data["prompt_word"],
            accepted_answers=word_data["accepted_answers"],
            position=word_data["position"],
        ))

    db.commit()
    return RedirectResponse(
        f"/groups/{group_id}/manage?success=vocab_created",
        status_code=302,
    )


@router.get("/{group_id:int}/lessons/{lesson_id:int}/vocabulary/{vocab_id:int}/edit", response_class=HTMLResponse)
def vocab_edit_page(
    group_id: int,
    lesson_id: int,
    vocab_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group or not _can_manage_group_content(user, group, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    lesson = db.query(GroupLesson).filter(
        GroupLesson.id == lesson_id,
        GroupLesson.group_id == group_id,
    ).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")

    vocab = db.query(VocabularySet).options(
        joinedload(VocabularySet.items)
    ).filter(
        VocabularySet.id == vocab_id,
        VocabularySet.lesson_id == lesson_id,
    ).first()
    if not vocab:
        raise HTTPException(status_code=404, detail="Словарь не найден")

    # Строим bulk-текст из существующих слов
    lines = []
    for item in sorted(vocab.items, key=lambda x: x.position):
        answers = item.accepted_answers or ""
        answers_display = answers.replace("|", "; ")
        lines.append(f"{item.prompt_word} = {answers_display}")
    words_bulk = "\n".join(lines)

    return templates.TemplateResponse("groups/vocabulary_edit.html", {
        "request": request,
        "user": user,
        "group": group,
        "lesson": lesson,
        "vocab": vocab,
        "words_bulk": words_bulk,
        "can_preview_as_owner": True,
    })


@router.post("/{group_id:int}/lessons/{lesson_id:int}/vocabulary/{vocab_id:int}/edit")
async def vocab_edit(
    group_id: int,
    lesson_id: int,
    vocab_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    words_bulk: str = Form(""),
    db: Session = Depends(get_db),
):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group or not _can_manage_group_content(user, group, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    vocab = db.query(VocabularySet).filter(
        VocabularySet.id == vocab_id,
        VocabularySet.lesson_id == lesson_id,
    ).first()
    if not vocab:
        raise HTTPException(status_code=404, detail="Словарь не найден")

    vocab.title = title.strip()
    vocab.description = description.strip() or None

    # Удаляем старые слова и создаём новые
    db.query(VocabularyItem).filter(VocabularyItem.vocab_set_id == vocab_id).delete()

    for word_data in parse_words_bulk(words_bulk):
        db.add(VocabularyItem(
            vocab_set_id=vocab.id,
            prompt_word=word_data["prompt_word"],
            accepted_answers=word_data["accepted_answers"],
            position=word_data["position"],
        ))

    db.commit()
    return RedirectResponse(
        f"/groups/{group_id}/manage?success=vocab_saved",
        status_code=302,
    )


@router.post("/{group_id:int}/lessons/{lesson_id:int}/vocabulary/{vocab_id:int}/delete")
def vocab_delete(
    group_id: int,
    lesson_id: int,
    vocab_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group or not _can_manage_group_content(user, group, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    vocab = db.query(VocabularySet).filter(
        VocabularySet.id == vocab_id,
        VocabularySet.lesson_id == lesson_id,
    ).first()
    if vocab:
        db.delete(vocab)
        db.commit()

    return RedirectResponse(f"/groups/{group_id}/manage", status_code=302)


# ═══════════════════════════════════════════════════════════
# VOCABULARY — ПРОСМОТР И ПРОХОЖДЕНИЕ (student)
# ═══════════════════════════════════════════════════════════

@router.get("/{group_id:int}/lessons/{lesson_id:int}/vocabulary/{vocab_id:int}", response_class=HTMLResponse)
def vocab_start_page(
    group_id: int,
    lesson_id: int,
    vocab_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user, redirect = _require_login(request, db)
    if redirect:
        return redirect

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    can_preview_as_owner = _can_manage_group_content(user, group, db)
    if not group.is_active and not can_preview_as_owner:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    membership = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.student_id == user.id,
    ).first()

    if not membership and not can_preview_as_owner:
        raise HTTPException(status_code=403, detail="Нет доступа к этой группе")

    lesson = db.query(GroupLesson).filter(
        GroupLesson.id == lesson_id,
        GroupLesson.group_id == group_id,
    ).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")

    vocab = db.query(VocabularySet).options(
        joinedload(VocabularySet.items)
    ).filter(
        VocabularySet.id == vocab_id,
        VocabularySet.lesson_id == lesson_id,
    ).first()
    if not vocab:
        raise HTTPException(status_code=404, detail="Словарь не найден")

    # Последняя попытка студента
    last_attempt = None
    if membership:
        last_attempt = (
            db.query(VocabularyAttempt)
            .options(load_only(
                VocabularyAttempt.id,
                VocabularyAttempt.completed_at,
                VocabularyAttempt.is_completed,
                VocabularyAttempt.retake_allowed,
                VocabularyAttempt.score,
                VocabularyAttempt.total,
            ))
            .filter(
                VocabularyAttempt.vocab_set_id == vocab_id,
                VocabularyAttempt.student_id == user.id,
            )
            .order_by(VocabularyAttempt.completed_at.desc())
            .first()
        )

    # Может ли студент начать/повторить:
    # - ещё не проходил (last_attempt is None), ИЛИ
    # - попытка не завершена (in_progress), ИЛИ
    # - преподаватель разрешил повтор именно для этой попытки (retake_allowed), ИЛИ
    # - админ/org смотрит предпросмотр (can_preview_as_owner)
    can_retake = can_preview_as_owner or (last_attempt is None) or (not last_attempt.is_completed) or last_attempt.retake_allowed

    return templates.TemplateResponse("groups/vocabulary_start.html", {
        "request": request,
        "user": user,
        "group": group,
        "lesson": lesson,
        "vocab": vocab,
        "last_attempt": last_attempt,
        "membership": membership,
        "can_preview_as_owner": can_preview_as_owner,
        "can_retake": can_retake,
    })


@router.get("/{group_id:int}/lessons/{lesson_id:int}/vocabulary/{vocab_id:int}/quiz", response_class=HTMLResponse)
def vocab_quiz_page(
    group_id: int,
    lesson_id: int,
    vocab_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user, redirect = _require_login(request, db)
    if redirect:
        return redirect

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    can_preview_as_owner = _can_manage_group_content(user, group, db)
    if not group.is_active and not can_preview_as_owner:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    membership = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.student_id == user.id,
    ).first()

    if not membership and not can_preview_as_owner:
        raise HTTPException(status_code=403, detail="Нет доступа к этой группе")

    lesson = db.query(GroupLesson).filter(
        GroupLesson.id == lesson_id,
        GroupLesson.group_id == group_id,
    ).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")

    vocab = db.query(VocabularySet).options(
        joinedload(VocabularySet.items)
    ).filter(
        VocabularySet.id == vocab_id,
        VocabularySet.lesson_id == lesson_id,
    ).first()
    if not vocab:
        raise HTTPException(status_code=404, detail="Словарь не найден")

    existing_answers_data = []
    attempt_id = None

    if membership and not can_preview_as_owner:
        latest_attempt = (
            db.query(VocabularyAttempt)
            .options(load_only(
                VocabularyAttempt.id,
                VocabularyAttempt.completed_at,
                VocabularyAttempt.is_completed,
                VocabularyAttempt.retake_allowed,
            ))
            .filter(
                VocabularyAttempt.vocab_set_id == vocab_id,
                VocabularyAttempt.student_id == user.id,
            )
            .order_by(VocabularyAttempt.completed_at.desc())
            .first()
        )

        if latest_attempt:
            if latest_attempt.is_completed:
                if not latest_attempt.retake_allowed:
                    # Редирект на стартовую страницу — там студент увидит результат
                    return RedirectResponse(
                        f"/groups/{group_id}/lessons/{lesson_id}/vocabulary/{vocab_id}",
                        status_code=302,
                    )
                else:
                    # Разрешен повтор: создаем новую попытку
                    previous_attempt_id = latest_attempt.id
                    should_clear_retake = latest_attempt.retake_allowed
                    attempt_id = create_vocabulary_attempt_record(db, vocab_id, user.id)
                    if should_clear_retake:
                        # Сбрасываем разрешение на предыдущей попытке, чтобы не было бесконечных повторов
                        db.query(VocabularyAttempt).filter(
                            VocabularyAttempt.id == previous_attempt_id,
                        ).update(
                            {VocabularyAttempt.retake_allowed: False},
                            synchronize_session=False,
                        )
                        db.commit()
            else:
                # Есть незавершенная попытка, продолжаем её
                attempt_id = latest_attempt.id
                existing_answers = (
                    db.query(VocabularyAttemptAnswer)
                    .filter(VocabularyAttemptAnswer.attempt_id == attempt_id)
                    .all()
                )
                existing_answers_data = [
                    {
                        "item_id": a.item_id,
                        "student_answer": a.student_answer,
                        "is_correct": a.is_correct
                    }
                    for a in existing_answers
                ]
        else:
            # Нет ни одной попытки, создаем первую
            attempt_id = create_vocabulary_attempt_record(db, vocab_id, user.id)

    items_data = [
        {
            "id": item.id,
            "prompt_word": item.prompt_word,
            "accepted_answers": item.accepted_answers or "",
            "accepted_answers_ru": item.accepted_answers_ru or "",
            "accepted_answers_tj": item.accepted_answers_tj or "",
        }
        for item in sorted(vocab.items, key=lambda x: x.position)
    ]

    return templates.TemplateResponse("groups/vocabulary_quiz.html", {
        "request": request,
        "user": user,
        "group": group,
        "lesson": lesson,
        "vocab": vocab,
        "items_json": json.dumps(items_data, ensure_ascii=False),
        "existing_answers_json": json.dumps(existing_answers_data, ensure_ascii=False),
        "attempt_id": attempt_id,
        "membership": membership,
    })


@router.post("/{group_id:int}/lessons/{lesson_id:int}/vocabulary/{vocab_id:int}/attempts/{attempt_id:int}/answer")
async def vocab_submit_answer(
    group_id: int,
    lesson_id: int,
    vocab_id: int,
    attempt_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user, redirect = _require_login(request, db)
    if redirect:
        raise HTTPException(status_code=401, detail="Not authenticated")

    attempt = db.query(VocabularyAttempt).filter(
        VocabularyAttempt.id == attempt_id,
        VocabularyAttempt.vocab_set_id == vocab_id,
        VocabularyAttempt.student_id == user.id,
    ).options(load_only(
        VocabularyAttempt.id,
        VocabularyAttempt.is_completed,
        VocabularyAttempt.lang_used,
    )).first()

    if not attempt or attempt.is_completed:
        from fastapi.responses import JSONResponse as _JSONResponse
        return _JSONResponse({"success": False, "detail": "Invalid or completed attempt"}, status_code=400)

    body = await request.json()
    item_id = body.get("item_id")
    student_answer = body.get("student_answer", "")
    is_correct = bool(body.get("is_correct"))
    lang = body.get("lang", "ru")
    
    attempt.lang_used = lang

    # Check if answer already exists
    existing_answer = db.query(VocabularyAttemptAnswer).filter(
        VocabularyAttemptAnswer.attempt_id == attempt.id,
        VocabularyAttemptAnswer.item_id == item_id
    ).first()

    if existing_answer:
        existing_answer.student_answer = student_answer
        existing_answer.is_correct = is_correct
    else:
        db.add(VocabularyAttemptAnswer(
            attempt_id=attempt.id,
            item_id=item_id,
            student_answer=student_answer,
            is_correct=is_correct,
        ))

    db.commit()
    from fastapi.responses import JSONResponse as _JSONResponse
    return _JSONResponse({"success": True})


@router.post("/{group_id:int}/lessons/{lesson_id:int}/vocabulary/{vocab_id:int}/attempts/{attempt_id:int}/anti-cheat/second-warning")
async def vocab_report_second_anticheat_warning(
    group_id: int,
    lesson_id: int,
    vocab_id: int,
    attempt_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user, redirect = _require_login(request, db)
    if redirect:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not user.is_student:
        raise HTTPException(status_code=403, detail="Only students can report vocabulary anti-cheat warnings")

    try:
        attempt = db.query(VocabularyAttempt).filter(
            VocabularyAttempt.id == attempt_id,
            VocabularyAttempt.vocab_set_id == vocab_id,
            VocabularyAttempt.student_id == user.id,
        ).options(load_only(
            VocabularyAttempt.id,
            VocabularyAttempt.is_completed,
            VocabularyAttempt.anti_cheat_flags_count,
            VocabularyAttempt.anti_cheat_teacher_visible,
            VocabularyAttempt.anti_cheat_last_flag_at,
        )).first()
    except DatabaseError as exc:
        db.rollback()
        if not is_vocabulary_anticheat_schema_mismatch(exc):
            raise
        return JSONResponse({"success": False, "detail": "Anti-cheat migration required"}, status_code=503)

    if not attempt:
        return JSONResponse({"success": False, "detail": "Attempt not found"}, status_code=404)
    if attempt.is_completed:
        return JSONResponse({"success": False, "detail": "Attempt is completed"}, status_code=400)
    if attempt.anti_cheat_teacher_visible:
        return JSONResponse({"success": True})

    try:
        updated_rows = (
            db.query(VocabularyAttempt)
            .filter(
                VocabularyAttempt.id == attempt.id,
                VocabularyAttempt.anti_cheat_teacher_visible.is_(False),
            )
            .update(
                {
                    VocabularyAttempt.anti_cheat_flags_count: max(attempt.anti_cheat_flags_count or 0, 2),
                    VocabularyAttempt.anti_cheat_teacher_visible: True,
                    VocabularyAttempt.anti_cheat_last_flag_at: datetime.utcnow(),
                },
                synchronize_session=False,
            )
        )
        if updated_rows:
            db.commit()
        else:
            db.rollback()
    except DatabaseError as exc:
        db.rollback()
        if not is_vocabulary_anticheat_schema_mismatch(exc):
            raise
        return JSONResponse({"success": False, "detail": "Anti-cheat migration required"}, status_code=503)

    return JSONResponse({"success": True})


@router.post("/{group_id:int}/lessons/{lesson_id:int}/vocabulary/{vocab_id:int}/attempts/{attempt_id:int}/complete")
async def vocab_complete(
    group_id: int,
    lesson_id: int,
    vocab_id: int,
    attempt_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user, redirect = _require_login(request, db)
    if redirect:
        raise HTTPException(status_code=401, detail="Not authenticated")

    attempt = db.query(VocabularyAttempt).filter(
        VocabularyAttempt.id == attempt_id,
        VocabularyAttempt.vocab_set_id == vocab_id,
        VocabularyAttempt.student_id == user.id,
    ).options(load_only(
        VocabularyAttempt.id,
        VocabularyAttempt.completed_at,
        VocabularyAttempt.is_completed,
        VocabularyAttempt.score,
        VocabularyAttempt.total,
    )).first()

    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    if attempt.is_completed:
        from fastapi.responses import JSONResponse as _JSONResponse
        return _JSONResponse({"success": True, "score": attempt.score, "total": attempt.total})

    # Recalculate score and total just to be safe
    answers = db.query(VocabularyAttemptAnswer).filter(
        VocabularyAttemptAnswer.attempt_id == attempt.id
    ).all()

    correct_count = sum(1 for a in answers if a.is_correct)
    total = len(answers)

    attempt.score = correct_count
    attempt.total = total
    attempt.is_completed = True
    attempt.completed_at = datetime.utcnow()
    response_score = attempt.score
    response_total = attempt.total

    db.commit()
    
    from fastapi.responses import JSONResponse as _JSONResponse
    return _JSONResponse({"success": True, "score": response_score, "total": response_total})


@router.get("/{group_id:int}/lessons/{lesson_id:int}/vocabulary/{vocab_id:int}/results", response_class=HTMLResponse)
def vocab_results_page(
    group_id: int,
    lesson_id: int,
    vocab_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group or not _can_manage_group_content(user, group, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    lesson = db.query(GroupLesson).filter(
        GroupLesson.id == lesson_id,
        GroupLesson.group_id == group_id,
    ).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")

    vocab = db.query(VocabularySet).filter(
        VocabularySet.id == vocab_id,
        VocabularySet.lesson_id == lesson_id,
    ).first()
    if not vocab:
        raise HTTPException(status_code=404, detail="Словарь не найден")

    attempts = (
        db.query(VocabularyAttempt)
        .options(
            load_only(
                VocabularyAttempt.id,
                VocabularyAttempt.student_id,
                VocabularyAttempt.score,
                VocabularyAttempt.total,
                VocabularyAttempt.is_completed,
                VocabularyAttempt.retake_allowed,
                VocabularyAttempt.completed_at,
            ),
            joinedload(VocabularyAttempt.student),
        )
        .filter(VocabularyAttempt.vocab_set_id == vocab_id)
        .order_by(VocabularyAttempt.completed_at.desc())
        .all()
    )

    return templates.TemplateResponse("groups/vocabulary_results.html", {
        "request": request,
        "user": user,
        "group": group,
        "lesson": lesson,
        "vocab": vocab,
        "attempts": attempts,
        "can_manage": True,
    })


# ═══════════════════════════════════════════════════════════
# VOCABULARY — Разрешить/запретить повторные попытки (teacher / org)
# ═══════════════════════════════════════════════════════════

@router.post("/{group_id:int}/lessons/{lesson_id:int}/vocabulary/{vocab_id:int}/toggle-retake")
async def vocab_toggle_retake(
    group_id: int,
    lesson_id: int,
    vocab_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Toggle retake_allowed on a specific student's latest vocabulary attempt. Only teacher/org can call this."""
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group or not _can_manage_group_content(user, group, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    vocab = db.query(VocabularySet).filter(
        VocabularySet.id == vocab_id,
        VocabularySet.lesson_id == lesson_id,
    ).first()
    if not vocab:
        raise HTTPException(status_code=404, detail="Словарь не найден")

    form_data = await request.form()
    student_id = form_data.get("student_id")
    if not student_id:
        raise HTTPException(status_code=400, detail="Missing student_id")

    latest_attempt = (
        db.query(VocabularyAttempt)
        .options(load_only(
            VocabularyAttempt.id,
            VocabularyAttempt.completed_at,
            VocabularyAttempt.retake_allowed,
        ))
        .filter(
            VocabularyAttempt.vocab_set_id == vocab_id,
            VocabularyAttempt.student_id == student_id,
        )
        .order_by(VocabularyAttempt.completed_at.desc())
        .first()
    )

    if latest_attempt:
        latest_attempt.retake_allowed = not latest_attempt.retake_allowed
        db.commit()

    return RedirectResponse(
        f"/groups/{group_id}/lessons/{lesson_id}/vocabulary/{vocab_id}/results",
        status_code=302,
    )
