from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.user import User
from app.models.course import Course

router = APIRouter()
templates = Jinja2Templates(directory="templates")


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

    if user.role.value == "teacher":
        return RedirectResponse("/dashboard/teacher", status_code=302)
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
        
    return templates.TemplateResponse("assessment.html", {"request": request, "user": user})


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
        
    score = q1 + q2 + q3 + q4 + q5
    
    if score <= 9:
        user_level = "Beginner"
    elif score <= 15:
        user_level = "Intermediate"
    else:
        user_level = "Advanced"
        
    user.level = user_level
    user.assessment_completed = True
    db.commit()
    
    return RedirectResponse("/courses/recommended", status_code=302)


@router.get("/dashboard/student", response_class=HTMLResponse)
def student_dashboard(request: Request, db: Session = Depends(get_db)):
    user, redirect = require_login(request, db)
    if redirect:
        return redirect
    if user.role.value != "student":
        return RedirectResponse("/dashboard/teacher", status_code=302)

    # All courses
    all_courses = db.query(Course).options(joinedload(Course.teacher)).all()
    
    # User progress
    from app.models.progress import Progress
    from app.models.lesson import Lesson
    user_progress = db.query(Progress).filter(Progress.student_id == user.id).all()
    
    lessons = db.query(Lesson).options(joinedload(Lesson.module)).all()
    lesson_to_course = {l.id: l.module.course_id for l in lessons if l.module}
    
    # Group progress by course
    from datetime import datetime
    course_progress_data = {}
    for p in user_progress:
        c_id = lesson_to_course.get(p.lesson_id)
        if c_id:
            pt_time = p.completed_at or datetime.min
            if c_id not in course_progress_data:
                course_progress_data[c_id] = {
                    "completed_lessons": set(),
                    "last_accessed_lesson_id": p.lesson_id,
                    "last_accessed_time": pt_time
                }
            if p.completed:
                course_progress_data[c_id]["completed_lessons"].add(p.lesson_id)
            
            if pt_time > course_progress_data[c_id]["last_accessed_time"]:
                course_progress_data[c_id]["last_accessed_time"] = pt_time
                course_progress_data[c_id]["last_accessed_lesson_id"] = p.lesson_id

    my_courses = []
    for c in all_courses:
        if c.id in course_progress_data:
            data = course_progress_data[c.id]
            total_lessons = sum(len(m.lessons) for m in c.modules)
            pct = int((len(data["completed_lessons"]) / total_lessons) * 100) if total_lessons > 0 else 0
            
            last_lesson = next((l for l in lessons if l.id == data["last_accessed_lesson_id"]), None)
            
            my_courses.append({
                "course": c,
                "progress_pct": pct,
                "last_lesson": last_lesson
            })

    return templates.TemplateResponse(
        "dashboard_student.html",
        {
            "request": request, 
            "user": user, 
            "my_courses": my_courses
        },
    )


@router.get("/dashboard/teacher", response_class=HTMLResponse)
def teacher_dashboard(request: Request, db: Session = Depends(get_db)):
    user, redirect = require_login(request, db)
    if redirect:
        return redirect
    if user.role.value != "teacher":
        return RedirectResponse("/dashboard/student", status_code=302)

    # Только курсы этого преподавателя (teacher уже загружен, eager load не нужен)
    courses = db.query(Course).filter(Course.teacher_id == user.id).all()
    
    # Загружаем категории для списка выбора
    from app.models.category import Category
    categories = db.query(Category).all()
    
    return templates.TemplateResponse(
        "dashboard_teacher.html",
        {"request": request, "user": user, "courses": courses, "categories": categories},
    )
