from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload
from collections import defaultdict

from app.database import get_db
from app.models.user import User
from app.models.course import Course
from app.models.module import Module

router = APIRouter()
from app.ui import templates


def require_login(request: Request, db: Session):
    """Возвращает пользователя или редирект на логин."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None, RedirectResponse("/login", status_code=302)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        request.session.clear()
        return None, RedirectResponse("/login", status_code=302)
    return user, None


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    """Перенаправляет на нужный дашборд в зависимости от роли."""
    user, redirect = require_login(request, db)
    if redirect:
        return redirect

    if user.is_teacher:
        return RedirectResponse("/dashboard/teacher", status_code=302)
    if user.role.value == "teacher_pending":
        return RedirectResponse("/register/pending", status_code=302)
    if user.is_admin:
        return RedirectResponse("/admin", status_code=302)
    if user.is_org:
        return RedirectResponse("/dashboard/organization", status_code=302)
    return RedirectResponse("/dashboard/student", status_code=302)


@router.get("/assessment", response_class=HTMLResponse)
def assessment_page(request: Request, db: Session = Depends(get_db)):
    """Страница оценки уровня."""
    user, redirect = require_login(request, db)
    if redirect:
        return redirect
    
    # Если уже прошел - редирект в дашборд
    if user.assessment_completed:
        return RedirectResponse("/dashboard", status_code=302)
        
    return templates.TemplateResponse("pages/assessment.html", {"request": request, "user": user})


@router.post("/assessment")
def process_assessment(
    request: Request,
    q1: int = Form(...),
    q2: int = Form(...),
    q3: int = Form(...),
    q4: int = Form(...),
    q5: int = Form(...),
    db: Session = Depends(get_db)
):
    """Обработка результатов оценки."""
    user, redirect = require_login(request, db)
    if redirect:
        return redirect
        
    from app.models.assessment import AssessmentResponse
    
    # Сохраняем ответы в отдельную таблицу
    response = db.query(AssessmentResponse).filter(AssessmentResponse.user_id == user.id).first()
    if not response:
        response = AssessmentResponse(user_id=user.id)
        db.add(response)
        
    response.q1_answer = q1
    response.q2_answer = q2
    response.q3_answer = q3
    response.q4_answer = q4
    response.q5_answer = q5
    
    score = q1 + q2 + q3 + q4 + q5
    
    if score <= 6:
        user_level = "Beginner"
    elif score <= 11:
        user_level = "Intermediate"
    else:
        user_level = "Advanced"
        
    user.level = user_level
    user.assessment_completed = True
    db.commit()
    
    return RedirectResponse("/courses/catalog", status_code=302)


@router.get("/dashboard/student", response_class=HTMLResponse)
def student_dashboard(request: Request, db: Session = Depends(get_db)):
    user, redirect = require_login(request, db)
    if redirect:
        return redirect
    if user.role.value != "student":
        return RedirectResponse("/dashboard/teacher", status_code=302)

    from app.models.progress import Progress
    from app.models.lesson import Lesson
    from app.models.organization import OrganizationStudent
    from datetime import datetime

    # Получаем активную организацию студента (если есть)
    student_org_link = db.query(OrganizationStudent).options(
        joinedload(OrganizationStudent.organization)
    ).filter(
        OrganizationStudent.student_id == user.id,
        OrganizationStudent.status.in_(["accepted", "pending"])
    ).first()

    # Проверяем, есть ли уведомления об удалении
    removed_links = db.query(OrganizationStudent).filter(
        OrganizationStudent.student_id == user.id,
        OrganizationStudent.status == "removed",
        OrganizationStudent.was_removed_notification == True
    ).all()

    show_removed_notification = False
    if removed_links:
        show_removed_notification = True
        for r_link in removed_links:
            r_link.was_removed_notification = False
        db.commit()

    user_progress = (
        db.query(Progress)
        .options(joinedload(Progress.lesson).joinedload(Lesson.module))
        .filter(Progress.student_id == user.id)
        .all()
    )

    course_progress_data = defaultdict(lambda: {
        "completed_lessons": set(),
        "last_accessed_lesson_id": None,
        "last_accessed_time": datetime.min,
    })
    course_ids = set()
    last_lesson_ids = set()

    for progress in user_progress:
        if not progress.lesson or not progress.lesson.module:
            continue
        course_id = progress.lesson.module.course_id
        course_ids.add(course_id)
        pt_time = progress.completed_at or datetime.min
        data = course_progress_data[course_id]
        if progress.completed:
            data["completed_lessons"].add(progress.lesson_id)

        if pt_time >= data["last_accessed_time"]:
            data["last_accessed_time"] = pt_time
            data["last_accessed_lesson_id"] = progress.lesson_id
            last_lesson_ids.add(progress.lesson_id)

    all_courses = (
        db.query(Course)
        .options(joinedload(Course.teacher), joinedload(Course.modules).joinedload(Module.lessons))
        .filter(Course.id.in_(course_ids))
        .all()
    ) if course_ids else []

    last_lessons = {
        lesson.id: lesson
        for lesson in db.query(Lesson).filter(Lesson.id.in_(last_lesson_ids)).all()
    } if last_lesson_ids else {}

    my_courses = []
    for c in all_courses:
        if c.id in course_progress_data:
            data = course_progress_data[c.id]
            total_lessons = sum(len(m.lessons) for m in c.modules)
            pct = int((len(data["completed_lessons"]) / total_lessons) * 100) if total_lessons > 0 else 0

            my_courses.append({
                "course": c,
                "progress_pct": pct,
                "last_lesson": last_lessons.get(data["last_accessed_lesson_id"])
            })

    return templates.TemplateResponse(
        "dashboard/student.html",
        {
            "request": request, 
            "user": user, 
            "my_courses": my_courses,
            "student_org_link": student_org_link,
            "show_removed_notification": show_removed_notification
        },
    )


@router.get("/dashboard/teacher", response_class=HTMLResponse)
def teacher_dashboard(request: Request, db: Session = Depends(get_db)):
    user, redirect = require_login(request, db)
    if redirect:
        return redirect
    if user.role.value not in ("teacher", "admin"):
        if user.role.value == "teacher_pending":
            return RedirectResponse("/register/pending", status_code=302)
        return RedirectResponse("/dashboard/student", status_code=302)

    # Только курсы этого преподавателя (teacher уже загружен, eager load не нужен)
    courses = db.query(Course).filter(Course.teacher_id == user.id).all()
    
    # Загружаем категории для списка выбора
    from app.models.category import Category
    categories = db.query(Category).order_by(Category.name).all()
    
    # Заявки и приглашения от организаций
    from app.models.organization import OrganizationTeacher
    pending_invites = db.query(OrganizationTeacher).options(joinedload(OrganizationTeacher.organization)).filter(
        OrganizationTeacher.teacher_id == user.id,
        OrganizationTeacher.status == "pending"
    ).all()
    
    # Все заявки этого преподавателя в организации (все статусы) — для секции "Мои заявки"
    teacher_applications = db.query(OrganizationTeacher).options(joinedload(OrganizationTeacher.organization)).filter(
        OrganizationTeacher.teacher_id == user.id
    ).order_by(OrganizationTeacher.created_at.desc()).all()

    return templates.TemplateResponse(
        "dashboard/teacher.html",
        {
            "request": request,
            "user": user,
            "courses": courses,
            "categories": categories,
            "pending_invites": pending_invites,
            "my_org_applications": teacher_applications,  # backward compat
            "teacher_applications": teacher_applications,
        },
    )
