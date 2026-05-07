# Роутер авторизации: регистрация, логин, выход
import os
import uuid
import shutil
from fastapi import APIRouter, Depends, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
import bcrypt
from typing import Optional

from app.database import get_db
from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationTeacher
from app.utils.rate_limit import limiter

router = APIRouter()
from app.ui import templates
DOCUMENT_MAX_BYTES = 10 * 1024 * 1024
DOCUMENT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}


def hash_password(password: str) -> str:
    """Хешируем пароль с помощью bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Проверяем пароль против bcrypt-хеша."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def get_current_user(request: Request, db: Session = Depends(get_db)):
    """Получить текущего пользователя из сессии."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()


def _validate_teacher_document(document: UploadFile | None) -> None:
    if not document or not document.filename:
        return

    ext = os.path.splitext(document.filename)[1].lower()
    if ext not in DOCUMENT_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Неверный формат документа")

    document.file.seek(0, os.SEEK_END)
    size = document.file.tell()
    document.file.seek(0)
    if size > DOCUMENT_MAX_BYTES:
        raise HTTPException(status_code=400, detail="Файл слишком большой")


# ── Страница регистрации ────────────────────────────────────────────────────

@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    user = request.session.get("user_id")
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse("auth/register.html", {"request": request})


@router.post("/register")
@limiter.limit("5/minute")
async def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    bio: str = Form(""),
    org_name: str = Form(""),
    org_phone: str = Form(""),
    org_description: str = Form(""),
    org_id: Optional[int] = Form(None),   # ID организации при регистрации учителя
    document: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    name = name.strip()
    email = email.strip().lower()
    password = password.strip()

    if not name:
        raise HTTPException(status_code=400, detail="Введите имя")
    if not email:
        raise HTTPException(status_code=400, detail="Введите email")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Пароль должен быть не менее 6 символов")

    # Проверяем, что пользователь с таким email не существует
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": "Пользователь с таким email уже существует"},
            status_code=400,
        )

    # Валидация роли
    if role not in ("student", "teacher", "organization"):
        raise HTTPException(status_code=400, detail="Неверная роль")

    if role == "organization" and not org_name.strip():
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": "Введите название организации"},
            status_code=400,
        )

    if role == "organization" and not org_phone.strip():
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": "Введите номер телефона"},
            status_code=400,
        )

    if role == "organization" and not org_description.strip():
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": "Добавьте краткое описание организации"},
            status_code=400,
        )

    # Определяем реальную роль и сохраняем документ
    actual_role = UserRole.student
    is_active = True
    doc_path = None
    user_bio = None

    if role == "teacher":
        actual_role = UserRole.teacher_pending
        is_active = False
        user_bio = bio.strip() if bio else None

        # Документ необязателен — сохраняем если есть
        if document and document.filename:
            _validate_teacher_document(document)
            os.makedirs("static/documents", exist_ok=True)
            filename = f"{uuid.uuid4().hex}_{document.filename}"
            save_path = f"static/documents/{filename}"
            with open(save_path, "wb") as buffer:
                shutil.copyfileobj(document.file, buffer)
            doc_path = "/" + save_path

    elif role == "organization":
        # Организации ждут одобрения — создаём неактивными
        actual_role = UserRole.organization
        is_active = False

    # Если это первый пользователь в базе данных, делаем его админом
    if db.query(User).count() == 0:
        actual_role = UserRole.admin
        is_active = True

    user = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
        role=actual_role,
        documents=doc_path,
        bio=user_bio,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Создаём запись организации со статусом pending
    if actual_role == UserRole.organization:
        org = Organization(
            user_id=user.id,
            name=org_name.strip(),
            phone=org_phone.strip(),
            description=org_description.strip(),
            status="pending",
        )
        db.add(org)
        db.commit()

        # Сессию НЕ сохраняем — организация ждёт одобрения
        return RedirectResponse("/register/pending-org", status_code=302)

    # Если учитель выбрал организацию при регистрации — создаём pending связь
    if actual_role == UserRole.teacher_pending and org_id:
        target_org = db.query(Organization).filter(
            Organization.id == org_id,
            Organization.status == "approved"
        ).first()
        if target_org:
            org_link = OrganizationTeacher(
                organization_id=target_org.id,
                teacher_id=user.id,
                status="pending"
            )
            db.add(org_link)
            db.commit()

    # Сохраняем сессию
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["user_role"] = user.role.value
    request.session["user_name"] = user.name

    # Если преподаватель — показать страницу ожидания
    if user.role == UserRole.teacher_pending:
        return RedirectResponse("/register/pending", status_code=302)

    # Студент → ассессмент или дашборд
    if user.is_student and not user.assessment_completed:
        return RedirectResponse("/assessment", status_code=302)

    return RedirectResponse("/dashboard", status_code=302)


# ── Страница ожидания для преподавателей ────────────────────────────────────

@router.get("/register/pending", response_class=HTMLResponse)
def register_pending(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    user = db.query(User).filter(User.id == user_id).first() if user_id else None
    return templates.TemplateResponse("auth/register_pending.html", {"request": request, "user": user})


# ── Страница ожидания для организаций ────────────────────────────────────────

@router.get("/register/pending-org", response_class=HTMLResponse)
def register_pending_org(request: Request):
    return templates.TemplateResponse("auth/register_pending_org.html", {"request": request})


# ── Страница входа ──────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.post("/login")
@limiter.limit("5/minute")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Неверный email или пароль"},
            status_code=401,
        )

    # Организации, ждущие одобрения, не могут войти
    if user.is_org and not user.is_active:
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Ваша организация ещё не одобрена администратором."},
            status_code=403,
        )

    # Проверяем, заблокирован ли пользователь или ждёт одобрения
    if not user.is_active:
        if user.role == UserRole.teacher_pending:
            error_msg = "Ваша заявка преподавателя всё ещё находится на рассмотрении."
        elif user.is_org:
            error_msg = "Ваша организация всё ещё находится на рассмотрении."
        else:
            error_msg = "Ваш аккаунт заблокирован. Обратитесь к администратору."
            
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": error_msg},
            status_code=403,
        )

    request.session.clear()
    request.session["user_id"] = user.id
    request.session["user_role"] = user.role.value
    request.session["user_name"] = user.name

    # teacher_pending → страница ожидания
    if user.role == UserRole.teacher_pending:
        return RedirectResponse("/register/pending", status_code=302)

    if user.is_student and not user.assessment_completed:
        return RedirectResponse("/assessment", status_code=302)

    return RedirectResponse("/dashboard", status_code=302)


# ── Выход ───────────────────────────────────────────────────────────────────

@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=302)
