import os
import re
import shutil
import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy import case, func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.database import get_db
from app.dependencies import get_user, is_teacher, is_student, is_admin, can
from app.models.user import User
from app.models.course import Course
from app.models.organization import Organization, OrganizationTeacher
from app.models.progress import Progress
from app.models.category import Category
from app.models.module import Module
from app.models.lesson import Lesson
from app.models.material import Material
from app.models.review import Review
from app.models.quiz import Quiz, Question
from app.config import CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
from app.quiz_flow import course_learning_url, course_progress_state, course_progress_state_from_obj, first_course_lesson_url, is_course_ready_for_quiz, is_module_ready_for_quiz
from app.utils.uploads import validate_upload_file

try:
    import cloudinary
    import cloudinary.uploader
except ModuleNotFoundError:
    cloudinary = None

router = APIRouter(prefix="/courses")
from app.ui import templates

COURSE_IMAGE_MAX_BYTES = 5 * 1024 * 1024
COURSE_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
COURSE_IMAGE_DIR = os.path.join("static", "uploads", "course_images")
COURSE_MATERIAL_DIR = os.path.join("static", "uploads")
COURSE_MATERIAL_MAX_BYTES = 15 * 1024 * 1024
COURSE_MATERIAL_EXTENSIONS = {".pdf", ".doc", ".docx", ".ppt", ".pptx"}

if cloudinary:
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True,
    )


def _plain_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"<[^>]+>", "", value).strip()


def get_teacher_org(teacher_id, db):
    org_teacher = db.query(OrganizationTeacher).filter(
        OrganizationTeacher.teacher_id == teacher_id,
        OrganizationTeacher.status == "accepted"
    ).first()
    if org_teacher:
        return db.query(Organization).filter(
            Organization.id == org_teacher.organization_id
        ).first()
    return None


def _can_manage_course_quiz_url(user: User, course: Course, db: Session) -> bool:
    if is_admin(user):
        return True
    if is_teacher(user):
        return course.teacher_id == user.id
    if user.role.value == "organization":
        org = db.query(Organization).filter(Organization.user_id == user.id).first()
        if not org:
            return False
        return db.query(OrganizationTeacher.id).filter(
            OrganizationTeacher.organization_id == org.id,
            OrganizationTeacher.teacher_id == course.teacher_id,
            OrganizationTeacher.status == "accepted",
        ).first() is not None
    return False


def _course_image_fs_path(image_url: str | None) -> str | None:
    if not image_url or not image_url.startswith("/static/"):
        return None
    relative = image_url.removeprefix("/static/")
    return os.path.join("static", relative)


def _course_image_public_id(image_url: str | None) -> str | None:
    if not image_url:
        return None

    parsed_url = urlparse(image_url)
    if "res.cloudinary.com" not in parsed_url.netloc:
        return None

    path_parts = [part for part in parsed_url.path.split("/") if part]
    try:
        upload_index = path_parts.index("upload")
    except ValueError:
        return None

    public_id_parts = path_parts[upload_index + 1:]
    if public_id_parts and re.fullmatch(r"v\d+", public_id_parts[0]):
        public_id_parts = public_id_parts[1:]
    if not public_id_parts:
        return None

    public_id = "/".join(public_id_parts)
    public_id, _ = os.path.splitext(public_id)
    return public_id


def _delete_course_image(image_url: str | None) -> None:
    public_id = _course_image_public_id(image_url)
    if public_id:
        try:
            cloudinary.uploader.destroy(public_id, invalidate=True, resource_type="image")
        except Exception:
            pass
        return

    path = _course_image_fs_path(image_url)
    if path and os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass


def _save_course_image(image: UploadFile | None) -> str | None:
    if not image or not image.filename:
        return None

    upload = validate_upload_file(
        image,
        allowed_extensions=COURSE_IMAGE_EXTENSIONS,
        max_bytes=COURSE_IMAGE_MAX_BYTES,
        invalid_type_message="Разрешены только JPG, JPEG, PNG и WEBP",
        too_large_message="Изображение должно быть не больше 5MB",
    )

    if cloudinary and CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
        try:
            upload_result = cloudinary.uploader.upload(
                image.file,
                folder="courses",
                resource_type="image",
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail="Не удалось загрузить изображение курса") from exc

        image_url = upload_result.get("secure_url")
        if not image_url:
            raise HTTPException(status_code=500, detail="Cloudinary не вернул ссылку на изображение")
        return image_url

    os.makedirs(COURSE_IMAGE_DIR, exist_ok=True)
    image.file.seek(0)
    filename = f"{uuid.uuid4().hex}{upload.extension}"
    save_path = os.path.join(COURSE_IMAGE_DIR, filename)
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)
    return f"/static/uploads/course_images/{filename}"


def _validate_course_material_upload(file: UploadFile) -> str:
    upload = validate_upload_file(
        file,
        allowed_extensions=COURSE_MATERIAL_EXTENSIONS,
        max_bytes=COURSE_MATERIAL_MAX_BYTES,
        missing_message="Не выбран файл",
    )
    return upload.extension


def _save_course_materials(files: list[UploadFile] | None, course_id: int, db: Session) -> None:
    if not files:
        return

    os.makedirs(COURSE_MATERIAL_DIR, exist_ok=True)
    for file in files:
        if not file.filename:
            continue

        upload = validate_upload_file(
            file,
            allowed_extensions=COURSE_MATERIAL_EXTENSIONS,
            max_bytes=COURSE_MATERIAL_MAX_BYTES,
            missing_message="Не выбран файл",
        )
        ext = upload.extension
        stored_name = upload.safe_filename
        filename = f"{uuid.uuid4().hex}_{stored_name}"
        save_path = os.path.join(COURSE_MATERIAL_DIR, filename)
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        db.add(Material(
            course_id=course_id,
            title=upload.original_filename,
            file_url="/" + save_path,
            file_type=ext.lstrip("."),
        ))
    db.commit()


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
    # ОПТИМИЗАЦИЯ: Избегаем N+1 query - вместо count() + all(), делаем одну query
    # Сначала выполняем единую query для получения всех результатов
    base_query = db.query(Course).options(joinedload(Course.teacher), joinedload(Course.category))
    
    if q:
        base_query = base_query.filter(Course.title.ilike(f"%{q}%"))
    if category_id:
        base_query = base_query.filter(Course.category_id == category_id)
    
    # Получаем полный результат (из которого потом посчитаем total)
    ordered_query = base_query.order_by(Course.rating.desc())
    
    # Получаем offset курсы (на текущей странице)
    courses = ordered_query.offset((page - 1) * per_page).limit(per_page).all()
    
    # Получаем total (не требует второго запроса, т.к. мы уже получили все отфильтрованные курсы)
    # ПРИМЕЧАНИЕ: Для больших датасетов рекомендуется использ. query.count() отдельно,
    # но с page-based pagination можно сначала получить count из первого запроса
    # Для корректного подсчёта total без доп. query используем func.count()
    # Получаем total
    from sqlalchemy import func
    total_query = db.query(func.count(Course.id))
    if q:
        total_query = total_query.filter(Course.title.ilike(f"%{q}%"))
    if category_id:
        total_query = total_query.filter(Course.category_id == category_id)
    total = total_query.scalar()

    categories = db.query(Category).order_by(Category.name).all()
    user = get_user(request, db)
    
    total_pages = (total + per_page - 1) // per_page

    return templates.TemplateResponse("courses/courses_list.html", {
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
            "description": _plain_text(c.description),
            "image": c.image,
            "teacher_name": c.teacher.name,
            "rating": c.rating,
            "level": c.level,
            "created_at": c.created_at.strftime("%d.%m.%Y"),
        }
        for c in courses
    ]


# ── Создание курса ───────────────────────────────────────────────────────────

@router.post("/create")
def create_course(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    category_id: int = Form(0),
    level: str = Form("Beginner"),
    image: UploadFile | None = File(None),
    files: list[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    user = get_user(request, db)
    if not user or user.role.value not in ("teacher", "admin"):
        if user and user.role.value == "teacher_pending":
            raise HTTPException(status_code=403, detail="Ваш аккаунт ещё не подтверждён")
        raise HTTPException(status_code=403, detail="Только преподаватели могут создавать курсы")

    title = title.strip()
    description = description.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Введите название курса")
    if files:
        for file in files:
            if file and file.filename:
                _validate_course_material_upload(file)

    course = Course(
        title=title,
        description=description or None,
        image=_save_course_image(image),
        level=level,
        teacher_id=user.id,
        category_id=category_id or None,
    )
    db.add(course)
    db.commit()
    db.refresh(course)

    _save_course_materials(files, course.id, db)

    from main import invalidate_courses_cache
    invalidate_courses_cache()
    return RedirectResponse(f"/courses/{course.id}/manage", status_code=302)


# ── NEW API: Google Forms Quiz URL Management ──────────────────────────────────

@router.post("/api/quiz-url")
async def save_quiz_url(
    request: Request,
    db: Session = Depends(get_db),
):
    """Save Google Forms URL for course/module/lesson"""
    user = get_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Parse form data
    form_data = await request.form()
    scope_name = form_data.get('scope_name', '').strip()
    try:
        scope_id = int(form_data.get('scope_id', 0))
    except:
        raise HTTPException(status_code=400, detail="Invalid scope_id")
    quiz_url = form_data.get('quiz_url', '').strip()
    
    if not quiz_url:
        raise HTTPException(status_code=400, detail="URL cannot be empty")
    
    # Validate it's a valid URL
    try:
        from urllib.parse import urlparse
        result = urlparse(quiz_url)
        if not all([result.scheme, result.netloc]):
            raise ValueError()
    except:
        raise HTTPException(status_code=400, detail="Invalid URL format")
    
    # Handle different scopes
    if scope_name == "course":
        course = db.query(Course).filter(Course.id == scope_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        if not _can_manage_course_quiz_url(user, course, db):
            raise HTTPException(status_code=403, detail="Unauthorized")
        course.quiz_url = quiz_url
    
    elif scope_name == "module":
        module = db.query(Module).options(joinedload(Module.course)).filter(Module.id == scope_id).first()
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")

        if not module.course or not _can_manage_course_quiz_url(user, module.course, db):
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        module.quiz_url = quiz_url
    
    elif scope_name == "lesson":
        lesson = (
            db.query(Lesson)
            .options(joinedload(Lesson.module).joinedload(Module.course))
            .filter(Lesson.id == scope_id)
            .first()
        )
        if not lesson:
            raise HTTPException(status_code=404, detail="Lesson not found")

        if not lesson.module:
            raise HTTPException(status_code=404, detail="Module not found")
        if not lesson.module.course or not _can_manage_course_quiz_url(user, lesson.module.course, db):
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        lesson.quiz_url = quiz_url
    
    else:
        raise HTTPException(status_code=400, detail="Invalid scope")
    
    db.commit()
    return JSONResponse({"success": True})


@router.delete("/api/quiz-url")
async def delete_quiz_url(
    request: Request,
    db: Session = Depends(get_db),
):
    """Delete Google Forms URL from course/module/lesson"""
    user = get_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Parse form data
    form_data = await request.form()
    scope_name = form_data.get('scope_name', '').strip()
    try:
        scope_id = int(form_data.get('scope_id', 0))
    except:
        raise HTTPException(status_code=400, detail="Invalid scope_id")
    
    # Handle different scopes
    if scope_name == "course":
        course = db.query(Course).filter(Course.id == scope_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        if not _can_manage_course_quiz_url(user, course, db):
            raise HTTPException(status_code=403, detail="Unauthorized")
        course.quiz_url = None
    
    elif scope_name == "module":
        module = db.query(Module).options(joinedload(Module.course)).filter(Module.id == scope_id).first()
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")

        if not module.course or not _can_manage_course_quiz_url(user, module.course, db):
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        module.quiz_url = None
    
    elif scope_name == "lesson":
        lesson = (
            db.query(Lesson)
            .options(joinedload(Lesson.module).joinedload(Module.course))
            .filter(Lesson.id == scope_id)
            .first()
        )
        if not lesson:
            raise HTTPException(status_code=404, detail="Lesson not found")

        if not lesson.module:
            raise HTTPException(status_code=404, detail="Module not found")
        if not lesson.module.course or not _can_manage_course_quiz_url(user, lesson.module.course, db):
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        lesson.quiz_url = None
    
    else:
        raise HTTPException(status_code=400, detail="Invalid scope")
    
    db.commit()
    return JSONResponse({"success": True})


# ── Страница курса ───────────────────────────────────────────────────────────

@router.get("/{course_id}", response_class=HTMLResponse)
def course_page(course_id: int, request: Request, db: Session = Depends(get_db)):
    course = (
        db.query(Course)
        .options(
            joinedload(Course.teacher),
            joinedload(Course.category),
            joinedload(Course.quiz).selectinload(Quiz.questions),
            selectinload(Course.modules).joinedload(Module.quiz).selectinload(Quiz.questions),
            selectinload(Course.modules).selectinload(Module.lessons).joinedload(Lesson.quiz),
            selectinload(Course.reviews).joinedload(Review.student),
            selectinload(Course.materials),
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
    module_quiz_states = {}
    course_quiz_unlocked = False
    course_quiz_passed = False
    learning_url = None
    course_has_progress = False
    if is_student(user):
        course_lesson_ids = [lesson.id for module in course.modules for lesson in module.lessons]
        progress_rows = (
            db.query(Progress)
            .filter(
                Progress.student_id == user.id,
                Progress.lesson_id.in_(course_lesson_ids),
            )
            .all()
        ) if course_lesson_ids else []
        progress_data = {p.lesson_id: p.completed for p in progress_rows}
        course_has_progress = bool(progress_rows)

        total_lessons = sum(len(m.lessons) for m in course.modules)
        done_lessons = sum(
            1 for m in course.modules for l in m.lessons if progress_data.get(l.id)
        )
        completion_pct = int(done_lessons / total_lessons * 100) if total_lessons > 0 else 0

        # Переиспользуем уже загруженный course, избегая второго запроса к БД
        completed_lesson_ids, passed_quiz_ids = course_progress_state_from_obj(db, user.id, course)
        module_quiz_states = {
            module.id: {
                "unlocked": bool(module.quiz and is_module_ready_for_quiz(module, completed_lesson_ids, passed_quiz_ids)),
                "passed": bool(module.quiz and module.quiz.id in passed_quiz_ids),
            }
            for module in course.modules
            if module.quiz
        }
        course_quiz_unlocked = bool(course.quiz and is_course_ready_for_quiz(course, completed_lesson_ids, passed_quiz_ids))
        course_quiz_passed = bool(course.quiz and course.quiz.id in passed_quiz_ids)
        course_has_progress = course_has_progress or bool(passed_quiz_ids)
        learning_url = course_learning_url(db, user.id, course)
    else:
        learning_url = first_course_lesson_url(course)

    # \u0423\u0436\u0435 \u043e\u0441\u0442\u0430\u0432\u043b\u044f\u043b \u043e\u0442\u0437\u044b\u0432?
    user_review = None
    if user:
        user_review = db.query(Review).filter(
            Review.student_id == user.id,
            Review.teacher_id == course.teacher_id,
        ).first()

    # \u0422\u043e\u043f-4 \u043e\u0442\u0437\u044b\u0432\u0430 \u043a\u0443\u0440\u0441\u0430 (\u0432\u0438\u0434\u043d\u044b \u0432\u0441\u0435\u043c)
    top_reviews = (
        db.query(Review)
        .filter(Review.course_id == course_id)
        .order_by(Review.rating.desc(), Review.created_at.desc())
        .limit(4)
        .all()
    )

    # \u041f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0442\u044c \u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0435\u043d\u0438\u0435 \u043e\u0442\u0437\u044b\u0432\u0430 \u043d\u0430 \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0435 \u043a\u0443\u0440\u0441\u0430?
    show_review_prompt = False
    if is_student(user) and not user_review:
        completed_teacher_lessons = (
            db.query(func.count(Progress.id))
            .join(Lesson, Progress.lesson_id == Lesson.id)
            .join(Module, Lesson.module_id == Module.id)
            .join(Course, Module.course_id == Course.id)
            .filter(
                Progress.student_id == user.id,
                Progress.completed == True,  # noqa: E712
                Course.teacher_id == course.teacher_id,
            )
            .scalar()
        ) or 0
        # Условие 1: 2+ уроков у этого преподавателя
        enough_lessons = completed_teacher_lessons >= 2
        # Условие 2: курс пройден полностью (даже если урок всего один)
        total_course_lessons = sum(len(m.lessons) for m in course.modules)
        course_fully_done = total_course_lessons > 0 and completion_pct == 100
        show_review_prompt = enough_lessons or course_fully_done

    teacher_org = get_teacher_org(course.teacher_id, db)

    return templates.TemplateResponse("courses/course_page.html", {
        "request": request,
        "course": course,
        "user": user,
        "progress_data": progress_data,
        "completion_pct": completion_pct,
        "module_quiz_states": module_quiz_states,
        "course_quiz_unlocked": course_quiz_unlocked,
        "course_quiz_passed": course_quiz_passed,
        "learning_url": learning_url,
        "course_has_progress": course_has_progress,
        "user_review": user_review,
        "top_reviews": top_reviews,
        "show_review_prompt": show_review_prompt,
        "teacher_org": teacher_org,
    })


# ── Страница управления курсом (teacher) ─────────────────────────────────────

@router.get("/{course_id}/manage", response_class=HTMLResponse)
def manage_course(course_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user(request, db)
    if not user or user.role.value not in ("teacher", "admin", "organization"):
        if user and user.role.value == "teacher_pending":
            return RedirectResponse("/register/pending", status_code=302)
        return RedirectResponse("/login", status_code=302)

    course = (
        db.query(Course)
        .options(
            joinedload(Course.quiz).selectinload(Quiz.questions).selectinload(Question.answers),
            selectinload(Course.modules).joinedload(Module.quiz).selectinload(Quiz.questions).selectinload(Question.answers),
            selectinload(Course.modules).selectinload(Module.lessons).selectinload(Lesson.materials),
            selectinload(Course.modules).selectinload(Module.lessons).joinedload(Lesson.quiz).selectinload(Quiz.questions).selectinload(Question.answers),
        )
        .filter(Course.id == course_id)
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")

    if user.role.value == "teacher" and course.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    if user.role.value == "organization":
        org = db.query(Organization).filter(Organization.user_id == user.id).first()
        if not org:
            raise HTTPException(status_code=403, detail="Организация не найдена")
        link = db.query(OrganizationTeacher).filter(
            OrganizationTeacher.organization_id == org.id,
            OrganizationTeacher.teacher_id == course.teacher_id,
            OrganizationTeacher.status == "accepted"
        ).first()
        if not link:
            raise HTTPException(status_code=403, detail="Этот курс не принадлежит преподавателю из вашего учебного центра")

    categories = db.query(Category).order_by(Category.name).all()

    # ── Подсчет активности студентов ──────────────────────────────────────────
    course_lesson_ids = [lesson.id for module in course.modules for lesson in module.lessons]
    total_lessons = len(course_lesson_ids)

    student_activity = []
    if total_lessons > 0:
        student_rows = (
            db.query(
                User,
                func.count(
                    func.distinct(
                        case((Progress.completed == True, Progress.lesson_id), else_=None)  # noqa: E712
                    )
                ).label("completed_count"),
                func.max(Progress.completed_at).label("last_active"),
            )
            .join(Progress, Progress.student_id == User.id)
            .filter(Progress.lesson_id.in_(course_lesson_ids))
            .group_by(User.id)
            .all()
        )

        for student, completed_count, last_activity in student_rows:
            pct = int((completed_count / total_lessons) * 100)
            student_activity.append({
                "student": student,
                "completed": completed_count,
                "total": total_lessons,
                "progress_pct": pct,
                "last_active": last_activity,
            })

    return templates.TemplateResponse("courses/course_manage.html", {
        "request": request,
        "course": course,
        "user": user,
        "categories": categories,
        "student_activity": student_activity
    })


# ── Редактирование курса ─────────────────────────────────────────────────────

@router.post("/{course_id}/edit")
def edit_course(
    course_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    category_id: int = Form(0),
    level: str = Form("Beginner"),
    remove_image: bool = Form(False),
    image: UploadFile | None = File(None),
    files: list[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    user = get_user(request, db)
    if not user or user.role.value not in ("teacher", "admin", "organization"):
        raise HTTPException(status_code=403)

    title = title.strip()
    description = description.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Введите название курса")
    if files:
        for file in files:
            if file and file.filename:
                _validate_course_material_upload(file)

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404)

    if user.role.value == "teacher" and course.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    if user.role.value == "organization":
        org = db.query(Organization).filter(Organization.user_id == user.id).first()
        if not org:
            raise HTTPException(status_code=403)
        link = db.query(OrganizationTeacher).filter(
            OrganizationTeacher.organization_id == org.id,
            OrganizationTeacher.teacher_id == course.teacher_id,
            OrganizationTeacher.status == "accepted"
        ).first()
        if not link:
            raise HTTPException(status_code=403, detail="Курс не принадлежит вашему учебному центру")

    course.title = title
    course.description = description or None
    course.level = level
    course.category_id = category_id or None

    new_image_path = _save_course_image(image)
    if new_image_path:
        if course.image:
            _delete_course_image(course.image)
        course.image = new_image_path
    elif remove_image and course.image:
        _delete_course_image(course.image)
        course.image = None

    db.commit()
    _save_course_materials(files, course.id, db)
    from main import invalidate_courses_cache
    invalidate_courses_cache()
    return RedirectResponse(f"/courses/{course_id}/manage", status_code=302)


# ── Удаление курса ───────────────────────────────────────────────────────────

@router.post("/{course_id}/delete")
def delete_course(course_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user(request, db)
    if not user or user.role.value not in ("teacher", "admin", "organization"):
        raise HTTPException(status_code=403)

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404)

    if user.role.value == "teacher" and course.teacher_id != user.id:
        raise HTTPException(status_code=403)

    if user.role.value == "organization":
        org = db.query(Organization).filter(Organization.user_id == user.id).first()
        if not org:
            raise HTTPException(status_code=403)
        link = db.query(OrganizationTeacher).filter(
            OrganizationTeacher.organization_id == org.id,
            OrganizationTeacher.teacher_id == course.teacher_id,
            OrganizationTeacher.status == "accepted"
        ).first()
        if not link:
            raise HTTPException(status_code=403)

    _delete_course_image(course.image)
    db.delete(course)
    db.commit()
    from main import invalidate_courses_cache
    invalidate_courses_cache()
    return RedirectResponse("/dashboard/teacher", status_code=302)


@router.get("/{course_id}/completed", response_class=HTMLResponse)
def course_completed(course_id: int, request: Request, db: Session = Depends(get_db)):
    course = (
        db.query(Course)
        .options(joinedload(Course.teacher))
        .filter(Course.id == course_id)
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")

    user = get_user(request, db)
    if not user or user.role.value != "student":
        return RedirectResponse("/login", status_code=302)

    state_course, completed_lesson_ids, passed_quiz_ids = course_progress_state(db, user.id, course.id)
    if not state_course:
        raise HTTPException(status_code=404, detail="Курс не найден")

    total_lessons = sum(len(module.lessons) for module in state_course.modules)
    done_lessons = sum(1 for lesson_id in completed_lesson_ids if lesson_id in {lesson.id for module in state_course.modules for lesson in module.lessons})
    completion_pct = int(done_lessons / total_lessons * 100) if total_lessons > 0 else 0
    course_finished = is_course_ready_for_quiz(state_course, completed_lesson_ids, passed_quiz_ids)
    if state_course.quiz:
        course_finished = course_finished and state_course.quiz.id in passed_quiz_ids

    if not course_finished and state_course.modules:
        return RedirectResponse(f"/courses/{course.id}", status_code=302)

    # Оставлял отзыв этому преподавателю?
    user_review = db.query(Review).filter(
        Review.student_id == user.id,
        Review.teacher_id == course.teacher_id,
    ).first()
    show_review_on_completion = user_review is None

    return templates.TemplateResponse("courses/course_completed.html", {
        "request": request,
        "user": user,
        "course": course,
        "completion_pct": completion_pct,
        "show_review_on_completion": show_review_on_completion,
    })


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

    material = (
        db.query(Material)
        .options(
            joinedload(Material.course),
            joinedload(Material.lesson).joinedload(Lesson.module),
        )
        .filter(Material.id == material_id)
        .first()
    )
    if not material:
        raise HTTPException(status_code=404)

    course_id = None
    if material.course_id:
        course = material.course
        if not course or (not is_admin(user) and course.teacher_id != user.id):
            raise HTTPException(status_code=403)
        course_id = course.id
    elif material.lesson_id:
        lesson = material.lesson
        if not lesson or not lesson.module:
            raise HTTPException(status_code=404)
        course = db.query(Course).filter(Course.id == lesson.module.course_id).first()
        if not course or (not is_admin(user) and course.teacher_id != user.id):
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
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404)
    if not _can_manage_course_quiz_url(user, course, db):
        raise HTTPException(status_code=403)
    return {"id": course.id, "title": course.title, "description": course.description, "level": course.level}
