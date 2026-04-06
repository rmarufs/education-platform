import os
import uuid
import shutil
from fastapi import APIRouter, Depends, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.user import User
from app.models.course import Course
from app.models.progress import Progress
from app.models.category import Category
from app.models.module import Module
from app.models.lesson import Lesson
from app.models.material import Material
from app.models.review import Review

router = APIRouter(prefix="/courses")
templates = Jinja2Templates(directory="templates")


def get_user(request: Request, db: Session) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()


# ── Каталог курсов с поиском и фильтром ─────────────────────────────────────

@router.get("/catalog", response_class=HTMLResponse)
def courses_catalog(
    request: Request,
    q: str = "",
    category_id: int = 0,
    page: int = 1,
    per_page: int = 9,
    db: Session = Depends(get_db),
):
    query = db.query(Course).options(joinedload(Course.teacher), joinedload(Course.category))
    if q:
        query = query.filter(Course.title.ilike(f"%{q}%"))
    if category_id:
        query = query.filter(Course.category_id == category_id)
        
    total = query.count()
    courses = query.order_by(Course.rating.desc()).offset((page - 1) * per_page).limit(per_page).all()
    categories = db.query(Category).order_by(Category.name).all()
    user = get_user(request, db)
    
    total_pages = (total + per_page - 1) // per_page

    return templates.TemplateResponse("courses_list.html", {
        "request": request,
        "courses": courses,
        "categories": categories,
        "q": q,
        "selected_category": category_id,
        "user": user,
        "page": page,
        "total_pages": total_pages,
    })


# ── JSON-список для API ──────────────────────────────────────────────────────

@router.get("/api/list")
def list_courses_api(q: str = "", db: Session = Depends(get_db)):
    query = db.query(Course).options(joinedload(Course.teacher))
    if q:
        query = query.filter(Course.title.ilike(f"%{q}%"))
    courses = query.all()
    return [
        {
            "id": c.id,
            "title": c.title,
            "description": c.description,
            "teacher_name": c.teacher.name,
            "rating": c.rating,
            "level": c.level,
            "created_at": c.created_at.strftime("%d.%m.%Y"),
        }
        for c in courses
    ]


# ── Рекомендованные курсы ────────────────────────────────────────────────────

@router.get("/recommended", response_class=HTMLResponse)
def recommended_courses(request: Request, db: Session = Depends(get_db)):
    user = get_user(request, db)
    if not user or user.role.value != "student":
        return RedirectResponse("/login", status_code=302)
        
    if not user.assessment_completed:
        return RedirectResponse("/assessment", status_code=302)
        
    query = db.query(Course).options(joinedload(Course.teacher))
    
    if user.level == "Beginner":
        query = query.filter(Course.level == "Beginner")
    elif user.level == "Intermediate":
        query = query.filter(Course.level.in_(["Beginner", "Intermediate"]))
    # Advanced gets everything, so no filter needed
    
    recommended = query.order_by(Course.rating.desc()).all()
    
    return templates.TemplateResponse("recommended_courses.html", {
        "request": request,
        "courses": recommended,
        "user": user
    })



# ── Страница курса ───────────────────────────────────────────────────────────

@router.get("/{course_id}", response_class=HTMLResponse)
def course_page(course_id: int, request: Request, db: Session = Depends(get_db)):
    course = (
        db.query(Course)
        .options(
            joinedload(Course.teacher),
            joinedload(Course.category),
            joinedload(Course.modules).joinedload(Module.lessons),
            joinedload(Course.reviews).joinedload(Review.student),
        )
        .filter(Course.id == course_id)
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")

    user = get_user(request, db)

    # Прогресс студента по этому курсу
    progress_data = {}
    completion_pct = 0
    if user and user.role.value == "student":
        from app.models.progress import Progress
        progress_rows = db.query(Progress).filter(Progress.student_id == user.id).all()
        progress_data = {p.lesson_id: p.completed for p in progress_rows}

        total_lessons = sum(len(m.lessons) for m in course.modules)
        done_lessons = sum(
            1 for m in course.modules for l in m.lessons if progress_data.get(l.id)
        )
        completion_pct = int(done_lessons / total_lessons * 100) if total_lessons > 0 else 0

    # Уже оставлял отзыв?
    user_review = None
    if user:
        user_review = db.query(Review).filter(
            Review.course_id == course_id, Review.student_id == user.id
        ).first()

    return templates.TemplateResponse("course_page.html", {
        "request": request,
        "course": course,
        "user": user,
        "progress_data": progress_data,
        "completion_pct": completion_pct,
        "user_review": user_review,
    })


# ── Страница управления курсом (teacher) ─────────────────────────────────────

@router.get("/{course_id}/manage", response_class=HTMLResponse)
def manage_course(course_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user(request, db)
    if not user or user.role.value not in ("teacher", "admin"):
        if user and user.role.value == "teacher_pending":
            return RedirectResponse("/register/pending", status_code=302)
        return RedirectResponse("/login", status_code=302)

    course = (
        db.query(Course)
        .options(
            joinedload(Course.modules).joinedload(Module.lessons).joinedload(Lesson.materials),
            joinedload(Course.modules).joinedload(Module.lessons).joinedload(Lesson.quiz),
        )
        .filter(Course.id == course_id, Course.teacher_id == user.id)
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")

    categories = db.query(Category).all()

    # ── Подсчет активности студентов ──────────────────────────────────────────
    course_lesson_ids = [lesson.id for module in course.modules for lesson in module.lessons]
    total_lessons = len(course_lesson_ids)

    student_activity = []
    if total_lessons > 0:
        active_student_ids = [s[0] for s in db.query(Progress.student_id).filter(
            Progress.lesson_id.in_(course_lesson_ids)
        ).distinct().all()]

        if active_student_ids:
            from sqlalchemy import func
            students = db.query(User).filter(User.id.in_(active_student_ids)).all()
            for s in students:
                completed_count = db.query(Progress).filter(
                    Progress.student_id == s.id,
                    Progress.lesson_id.in_(course_lesson_ids),
                    Progress.completed == True
                ).count()
                
                last_activity = db.query(func.max(Progress.completed_at)).filter(
                    Progress.student_id == s.id,
                    Progress.lesson_id.in_(course_lesson_ids)
                ).scalar()

                pct = int((completed_count / total_lessons) * 100)
                student_activity.append({
                    "student": s,
                    "completed": completed_count,
                    "total": total_lessons,
                    "progress_pct": pct,
                    "last_active": last_activity
                })

    return templates.TemplateResponse("course_manage.html", {
        "request": request,
        "course": course,
        "user": user,
        "categories": categories,
        "student_activity": student_activity
    })


# ── Создание курса ───────────────────────────────────────────────────────────

@router.post("/create")
def create_course(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    category_id: int = Form(0),
    level: str = Form("Beginner"),
    files: list[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    user = get_user(request, db)
    if not user or user.role.value not in ("teacher", "admin"):
        if user and user.role.value == "teacher_pending":
            raise HTTPException(status_code=403, detail="Ваш аккаунт ещё не подтверждён")
        raise HTTPException(status_code=403, detail="Только преподаватели могут создавать курсы")

    course = Course(
        title=title,
        description=description,
        level=level,
        teacher_id=user.id,
        category_id=category_id or None,
    )
    db.add(course)
    db.commit()
    db.refresh(course)

    if files:
        for file in files:
            if file.filename:
                ext = file.filename.split('.')[-1]
                save_path = f"static/uploads/{uuid.uuid4().hex}_{file.filename}"
                os.makedirs("static/uploads", exist_ok=True)
                with open(save_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                
                material = Material(
                    course_id=course.id,
                    title=file.filename,
                    file_url="/" + save_path,
                    file_type=ext
                )
                db.add(material)
        db.commit()

    return RedirectResponse(f"/courses/{course.id}/manage", status_code=302)


# ── Редактирование курса ─────────────────────────────────────────────────────

@router.post("/{course_id}/edit")
def edit_course(
    course_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    category_id: int = Form(0),
    level: str = Form("Beginner"),
    files: list[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    user = get_user(request, db)
    if not user or user.role.value not in ("teacher", "admin"):
        raise HTTPException(status_code=403)

    course = db.query(Course).filter(Course.id == course_id, Course.teacher_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404)

    course.title = title
    course.description = description
    course.level = level
    course.category_id = category_id or None

    if files:
        for file in files:
            if file.filename:
                ext = file.filename.split('.')[-1]
                save_path = f"static/uploads/{uuid.uuid4().hex}_{file.filename}"
                os.makedirs("static/uploads", exist_ok=True)
                with open(save_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                
                material = Material(
                    course_id=course.id,
                    title=file.filename,
                    file_url="/" + save_path,
                    file_type=ext
                )
                db.add(material)

    db.commit()
    return RedirectResponse(f"/courses/{course_id}/manage", status_code=302)


# ── Удаление курса ───────────────────────────────────────────────────────────

@router.post("/{course_id}/delete")
def delete_course(course_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user(request, db)
    if not user or user.role.value not in ("teacher", "admin"):
        raise HTTPException(status_code=403)

    course = db.query(Course).filter(Course.id == course_id, Course.teacher_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404)

    db.delete(course)
    db.commit()
    return RedirectResponse("/dashboard/teacher", status_code=302)


# ── Удаление материала ───────────────────────────────────────────────────────

@router.post("/materials/{material_id}/delete")
def delete_course_material(
    material_id: int, 
    request: Request, 
    db: Session = Depends(get_db)
):
    user = get_user(request, db)
    if not user or user.role.value not in ("teacher", "admin"):
        raise HTTPException(status_code=403)

    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404)

    course_id = None
    if material.course_id:
        course = db.query(Course).filter(Course.id == material.course_id).first()
        if not course or course.teacher_id != user.id:
            raise HTTPException(status_code=403)
        course_id = course.id
    elif material.lesson_id:
        lesson = db.query(Lesson).options(joinedload(Lesson.module)).filter(Lesson.id == material.lesson_id).first()
        if lesson:
            course = db.query(Course).filter(Course.id == lesson.module.course_id).first()
            if not course or course.teacher_id != user.id:
                raise HTTPException(status_code=403)
            course_id = course.id

    if material.file_url:
        file_path = material.file_url.lstrip("/")
        if os.path.exists(file_path):
            os.remove(file_path)

    db.delete(material)
    db.commit()

    if course_id:
        return RedirectResponse(f"/courses/{course_id}/manage", status_code=302)
    return RedirectResponse("/dashboard/teacher", status_code=302)


# ── API JSON для редактирования ──────────────────────────────────────────────

@router.get("/api/{course_id}")
def get_course_api(course_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user(request, db)
    if not user:
        raise HTTPException(status_code=401)
    course = db.query(Course).filter(Course.id == course_id, Course.teacher_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404)
    return {"id": course.id, "title": course.title, "description": course.description, "level": course.level}
