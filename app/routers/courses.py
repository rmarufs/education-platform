import os
import re
import shutil
from urllib.parse import urlparse

import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, Depends, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import case, func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.database import get_db
from app.models.user import User
from app.models.course import Course
from app.models.progress import Progress
from app.models.category import Category
from app.models.module import Module
from app.models.lesson import Lesson
from app.models.material import Material
from app.models.review import Review
from app.config import CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET

router = APIRouter(prefix="/courses")
templates = Jinja2Templates(directory="templates")

COURSE_IMAGE_MAX_BYTES = 5 * 1024 * 1024
COURSE_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
COURSE_MATERIAL_DIR = os.path.join("static", "uploads")
COURSE_MATERIAL_MAX_BYTES = 15 * 1024 * 1024
COURSE_MATERIAL_EXTENSIONS = {".pdf", ".doc", ".docx", ".ppt", ".pptx"}

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


def get_user(request: Request, db: Session) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()


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

    ext = os.path.splitext(image.filename)[1].lower()
    if ext not in COURSE_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Разрешены только JPG, JPEG, PNG и WEBP")

    image.file.seek(0, os.SEEK_END)
    size = image.file.tell()
    image.file.seek(0)
    if size > COURSE_IMAGE_MAX_BYTES:
        raise HTTPException(status_code=400, detail="Изображение должно быть не больше 5MB")

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


def _validate_course_material_upload(file: UploadFile) -> str:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Не выбран файл")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in COURSE_MATERIAL_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Недопустимый тип файла")

    file.file.seek(0, os.SEEK_END)
    size = file.file.tell()
    file.file.seek(0)
    if size > COURSE_MATERIAL_MAX_BYTES:
        raise HTTPException(status_code=400, detail="Файл слишком большой")
    return ext


def _save_course_materials(files: list[UploadFile] | None, course_id: int, db: Session) -> None:
    if not files:
        return

    os.makedirs(COURSE_MATERIAL_DIR, exist_ok=True)
    for file in files:
        if not file.filename:
            continue

        ext = _validate_course_material_upload(file)
        original_name = os.path.basename(file.filename)
        filename = f"{uuid.uuid4().hex}_{original_name}"
        save_path = os.path.join(COURSE_MATERIAL_DIR, filename)
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        db.add(Material(
            course_id=course_id,
            title=original_name,
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
            "description": _plain_text(c.description),
            "image": c.image,
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
        
    query = db.query(Course).options(joinedload(Course.teacher), joinedload(Course.category))
    
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
            selectinload(Course.modules).selectinload(Module.lessons),
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
    if user and user.role.value == "student":
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
            selectinload(Course.modules).selectinload(Module.lessons).selectinload(Lesson.materials),
            selectinload(Course.modules).selectinload(Module.lessons).joinedload(Lesson.quiz),
        )
        .filter(Course.id == course_id, Course.teacher_id == user.id)
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")

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
    remove_image: bool = Form(False),
    image: UploadFile | None = File(None),
    files: list[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    user = get_user(request, db)
    if not user or user.role.value not in ("teacher", "admin"):
        raise HTTPException(status_code=403)

    title = title.strip()
    description = description.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Введите название курса")
    if files:
        for file in files:
            if file and file.filename:
                _validate_course_material_upload(file)

    course = db.query(Course).filter(Course.id == course_id, Course.teacher_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404)

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

    _delete_course_image(course.image)
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
        if not course or course.teacher_id != user.id:
            raise HTTPException(status_code=403)
        course_id = course.id
    elif material.lesson_id:
        lesson = material.lesson
        if not lesson or not lesson.module:
            raise HTTPException(status_code=404)
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
