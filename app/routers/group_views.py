from typing import Optional

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.ui import templates
from app.models.group import (
    Group, GroupMember, GroupModule, GroupLesson, GroupLessonProgress, GroupJournalEntry
)
from app.models.vocabulary import VocabularySet, VocabularyAttempt
from app.models.user import User
from app.models.organization import Organization, OrganizationTeacher, OrganizationStudent
from app.deps.auth import get_user as _get_user

from app.services.group_lesson_service import ordered_group_lessons as _ordered_group_lessons

router = APIRouter()

def _require_login(request: Request, db: Session):
    user = _get_user(request, db)
    if not user:
        return None, RedirectResponse("/login", status_code=302)
    return user, None


def _require_teacher(request: Request, db: Session):
    user = _get_user(request, db)
    if not user or not user.is_teacher:
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


@router.get("/{group_id:int}/manage", response_class=HTMLResponse)
def group_manage(group_id: int, request: Request, db: Session = Depends(get_db)):
    """Управление группой: организация видит всё, преподаватель — уроки и учеников."""
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    success = request.query_params.get("success")
    error = request.query_params.get("error")

    if user.is_org:
        org = db.query(Organization).filter(Organization.user_id == user.id).first()
        group = db.query(Group).options(
            joinedload(Group.organization),
            joinedload(Group.teacher),
            joinedload(Group.modules).joinedload(GroupModule.lessons).joinedload(GroupLesson.materials),
            joinedload(Group.modules).joinedload(GroupModule.lessons).joinedload(GroupLesson.homework),
            joinedload(Group.members).joinedload(GroupMember.student),
            joinedload(Group.lessons).joinedload(GroupLesson.materials),
            joinedload(Group.lessons).joinedload(GroupLesson.group_module),
            joinedload(Group.lessons).joinedload(GroupLesson.homework),
        ).filter(
            Group.id == group_id,
            Group.organization_id == org.id,
        ).first()
        if not group:
            raise HTTPException(status_code=404, detail="Группа не найдена")

        # Teachers in this org for dropdown
        teacher_links = db.query(OrganizationTeacher).options(
            joinedload(OrganizationTeacher.teacher)
        ).filter(
            OrganizationTeacher.organization_id == org.id,
            OrganizationTeacher.status == "accepted",
        ).all()
        org_teachers = [link.teacher for link in teacher_links]

        # Accepted students in this org (not yet in group)
        org_student_links = db.query(OrganizationStudent).options(
            joinedload(OrganizationStudent.student)
        ).filter(
            OrganizationStudent.organization_id == org.id,
            OrganizationStudent.status == "accepted",
        ).all()
        member_ids = {m.student_id for m in group.members}
        available_students = [
            s.student for s in org_student_links if s.student_id not in member_ids
        ]

        return templates.TemplateResponse("groups/manage.html", {
            "request": request,
            "user": user,
            "org": org,
            "group": group,
            "group_modules": group.modules,
            "org_teachers": org_teachers,
            "available_students": available_students,
            "success": success,
            "error": error,
        })

    elif user.is_teacher:
        group = db.query(Group).options(
            joinedload(Group.organization),
            joinedload(Group.teacher),
            joinedload(Group.modules).joinedload(GroupModule.lessons).joinedload(GroupLesson.materials),
            joinedload(Group.modules).joinedload(GroupModule.lessons).joinedload(GroupLesson.homework),
            joinedload(Group.members).joinedload(GroupMember.student),
            joinedload(Group.lessons).joinedload(GroupLesson.materials),
            joinedload(Group.lessons).joinedload(GroupLesson.group_module),
            joinedload(Group.lessons).joinedload(GroupLesson.homework),
        ).filter(
            Group.id == group_id,
            Group.teacher_id == user.id,
        ).first()
        if not group:
            raise HTTPException(status_code=403, detail="Доступ запрещён")

        return templates.TemplateResponse("groups/teacher_view.html", {
            "request": request,
            "user": user,
            "group": group,
            "group_modules": group.modules,
            "success": success,
            "error": error,
        })

    else:
        raise HTTPException(status_code=403, detail="Доступ запрещён")



@router.get("/{group_id:int}/teach", response_class=HTMLResponse)
def group_teach(group_id: int, request: Request, db: Session = Depends(get_db)):
    """Lesson selection for the assigned teacher's in-class mode."""
    user, redirect = _require_teacher(request, db)
    if redirect:
        return redirect

    group = db.query(Group).options(
        joinedload(Group.organization),
        joinedload(Group.teacher),
        joinedload(Group.modules).joinedload(GroupModule.lessons).joinedload(GroupLesson.homework),
        joinedload(Group.lessons).joinedload(GroupLesson.group_module),
        joinedload(Group.lessons).joinedload(GroupLesson.homework),
    ).filter(
        Group.id == group_id,
        Group.teacher_id == user.id,
        Group.is_active == True,  # noqa: E712
    ).first()
    if not group:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    return templates.TemplateResponse("groups/teach.html", {
        "request": request,
        "user": user,
        "group": group,
        "group_modules": group.modules,
        "ordered_lessons": _ordered_group_lessons(group),
    })



@router.get("/{group_id:int}/view", response_class=HTMLResponse)
def group_student_view(group_id: int, request: Request, db: Session = Depends(get_db)):
    """Просмотр группы для участника-студента."""
    user, redirect = _require_login(request, db)
    if redirect:
        return redirect

    group = db.query(Group).options(
        joinedload(Group.organization),
        joinedload(Group.modules).joinedload(GroupModule.lessons).joinedload(GroupLesson.materials),
        joinedload(Group.lessons).joinedload(GroupLesson.materials),
        joinedload(Group.teacher),
    ).filter(Group.id == group_id, Group.is_active == True).first()

    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    # Check membership
    membership = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.student_id == user.id,
    ).first()

    if not membership:
        return RedirectResponse("/dashboard/student?error=access_denied", status_code=302)

    ordered_lessons = _ordered_group_lessons(group)
    ordered_lesson_ids = [lesson.id for lesson in ordered_lessons]
    group_has_progress = False
    if ordered_lesson_ids:
        completed_lesson = (
            db.query(GroupLessonProgress.id)
            .filter(
                GroupLessonProgress.group_id == group_id,
                GroupLessonProgress.student_id == user.id,
                GroupLessonProgress.lesson_id.in_(ordered_lesson_ids),
            )
            .first()
        )
        journal_progress = (
            db.query(GroupJournalEntry.id)
            .filter(
                GroupJournalEntry.group_id == group_id,
                GroupJournalEntry.student_id == user.id,
                GroupJournalEntry.lesson_id.in_(ordered_lesson_ids),
                (GroupJournalEntry.present == True) | (GroupJournalEntry.grade.isnot(None)),  # noqa: E712
            )
            .first()
        )
        vocab_progress = (
            db.query(VocabularyAttempt.id)
            .join(VocabularySet, VocabularyAttempt.vocab_set_id == VocabularySet.id)
            .filter(
                VocabularyAttempt.student_id == user.id,
                VocabularySet.lesson_id.in_(ordered_lesson_ids),
            )
            .first()
        )
        group_has_progress = bool(completed_lesson or journal_progress or vocab_progress)
    return templates.TemplateResponse("groups/student_view.html", {
        "request": request,
        "user": user,
        "group": group,
        "group_modules": group.modules,
        "ordered_lessons": ordered_lessons,
        "group_has_progress": group_has_progress,
        "membership": membership,
    })


    next_url = request.query_params.get("next")
    allowed_prefixes = (
        f"/groups/{group_id}/lessons/",
    )
    if next_url and next_url.startswith(allowed_prefixes):
        return RedirectResponse(next_url, status_code=302)

    return RedirectResponse("/dashboard/student", status_code=302)



