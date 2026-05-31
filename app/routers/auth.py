# Роутер авторизации: регистрация, логин, выход
import os
import re
import uuid
import shutil
from datetime import date
from fastapi import APIRouter, Depends, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
import bcrypt
from typing import Optional

from app.database import get_db
from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationTeacher, OrganizationStudent
from app.utils.rate_limit import limiter
from app.utils.uploads import validate_upload_file

router = APIRouter()
from app.ui import templates
DOCUMENT_MAX_BYTES = 10 * 1024 * 1024
DOCUMENT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}
PHONE_RE = re.compile(r"^\+?[0-9][0-9\s().-]{6,24}$")


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


def _validate_teacher_document(document: UploadFile | None):
    if not document or not document.filename:
        return None

    return validate_upload_file(
        document,
        allowed_extensions=DOCUMENT_EXTENSIONS,
        max_bytes=DOCUMENT_MAX_BYTES,
        invalid_type_message="Неверный формат документа",
    )


def _is_valid_phone(value: str) -> bool:
    return bool(PHONE_RE.fullmatch(value.strip()))


def _register_context(
    request: Request,
    role: str,
    form_values: dict | None = None,
    error_key: str | None = None,
    error: str | None = None,
    error_field: str | None = None,
    error_step: int | None = None,
) -> dict:
    context = {
        "request": request,
        "selected_role": role,
        "form_values": form_values or {},
    }
    if error_key:
        context["error_key"] = error_key
    if error:
        context["error"] = error
    if error_field:
        context["error_field"] = error_field
    if error_step:
        context["error_step"] = error_step
    return context


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
    name: str = Form(""),
    first_name: str = Form(""),
    last_name: str = Form(""),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    birth_date: str = Form(""),
    phone_number: str = Form(""),
    parent_contact_name: str = Form(""),
    parent_contact_phone: str = Form(""),
    bio: str = Form(""),
    org_name: str = Form(""),
    org_phone: str = Form(""),
    org_description: str = Form(""),
    org_id: Optional[int] = Form(None),          # ID организации при регистрации учителя
    student_org_id: Optional[int] = Form(None),  # ID организации при регистрации студента
    gender: Optional[str] = Form(None),          # пол
    document: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    first_name = first_name.strip()
    last_name = last_name.strip()
    name = name.strip()
    if role == "student":
        name = " ".join(part for part in (first_name, last_name) if part)
    email = email.strip().lower()
    password = password.strip()
    birth_date = birth_date.strip()
    phone_number = phone_number.strip()
    parent_contact_name = parent_contact_name.strip()
    parent_contact_phone = parent_contact_phone.strip()
    form_values = {
        "name": name,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "role": role,
        "birth_date": birth_date,
        "phone_number": phone_number,
        "parent_contact_name": parent_contact_name,
        "parent_contact_phone": parent_contact_phone,
        "bio": bio,
        "org_name": org_name,
        "org_phone": org_phone,
        "org_description": org_description,
        "org_id": org_id or "",
        "student_org_id": student_org_id or "",
        "gender": gender or "",
    }

    if role == "student" and not first_name:
        return templates.TemplateResponse(
            "auth/register.html",
            _register_context(
                request,
                role,
                form_values,
                error_key="validation.first_name_required",
                error_field="first_name",
                error_step=1,
            ),
            status_code=400,
        )
    if role == "student" and not last_name:
        return templates.TemplateResponse(
            "auth/register.html",
            _register_context(
                request,
                role,
                form_values,
                error_key="validation.last_name_required",
                error_field="last_name",
                error_step=1,
            ),
            status_code=400,
        )
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
            _register_context(
                request,
                role,
                form_values,
                error="Пользователь с таким email уже существует",
                error_field="email" if role == "student" else None,
                error_step=4 if role == "student" else None,
            ),
            status_code=400,
        )

    # Валидация роли
    if role not in ("student", "teacher", "organization"):
        raise HTTPException(status_code=400, detail="Неверная роль")

    if role in ("student", "teacher") and gender not in ("male", "female"):
        return templates.TemplateResponse(
            "auth/register.html",
            _register_context(
                request,
                role,
                form_values,
                error_key="validation.gender_required",
                error_field="gender",
                error_step=1 if role == "student" else None,
            ),
            status_code=400,
        )

    if role == "organization" and not org_name.strip():
        return templates.TemplateResponse(
            "auth/register.html",
            _register_context(request, role, form_values, error="Введите название учебного центра"),
            status_code=400,
        )

    if role == "organization" and not org_phone.strip():
        return templates.TemplateResponse(
            "auth/register.html",
            _register_context(request, role, form_values, error="Введите номер телефона"),
            status_code=400,
        )

    if role == "organization" and not org_description.strip():
        return templates.TemplateResponse(
            "auth/register.html",
            _register_context(request, role, form_values, error="Добавьте краткое описание учебного центра"),
            status_code=400,
        )

    parsed_birth_date = None
    if role == "student":
        if not birth_date:
            return templates.TemplateResponse(
                "auth/register.html",
                _register_context(
                    request,
                    role,
                    form_values,
                    error_key="validation.birth_date_required",
                    error_field="birth_date",
                    error_step=2,
                ),
                status_code=400,
            )
        try:
            parsed_birth_date = date.fromisoformat(birth_date)
        except ValueError:
            return templates.TemplateResponse(
                "auth/register.html",
                _register_context(
                    request,
                    role,
                    form_values,
                    error_key="validation.birth_date_invalid",
                    error_field="birth_date",
                    error_step=2,
                ),
                status_code=400,
            )
        if parsed_birth_date > date.today() or parsed_birth_date.year < 1900:
            return templates.TemplateResponse(
                "auth/register.html",
                _register_context(
                    request,
                    role,
                    form_values,
                    error_key="validation.birth_date_invalid",
                    error_field="birth_date",
                    error_step=2,
                ),
                status_code=400,
            )
        if not phone_number:
            return templates.TemplateResponse(
                "auth/register.html",
                _register_context(
                    request,
                    role,
                    form_values,
                    error_key="validation.student_phone_required",
                    error_field="phone_number",
                    error_step=2,
                ),
                status_code=400,
            )
        if not _is_valid_phone(phone_number):
            return templates.TemplateResponse(
                "auth/register.html",
                _register_context(
                    request,
                    role,
                    form_values,
                    error_key="auth.invalid_phone",
                    error_field="phone_number",
                    error_step=2,
                ),
                status_code=400,
            )
        if not parent_contact_name:
            return templates.TemplateResponse(
                "auth/register.html",
                _register_context(
                    request,
                    role,
                    form_values,
                    error_key="validation.parent_name_required",
                    error_field="parent_contact_name",
                    error_step=3,
                ),
                status_code=400,
            )
        if not parent_contact_phone:
            return templates.TemplateResponse(
                "auth/register.html",
                _register_context(
                    request,
                    role,
                    form_values,
                    error_key="validation.parent_phone_required",
                    error_field="parent_contact_phone",
                    error_step=3,
                ),
                status_code=400,
            )
        if not _is_valid_phone(parent_contact_phone):
            return templates.TemplateResponse(
                "auth/register.html",
                _register_context(
                    request,
                    role,
                    form_values,
                    error_key="auth.invalid_phone",
                    error_field="parent_contact_phone",
                    error_step=3,
                ),
                status_code=400,
            )

    selected_student_org = None
    if role == "student" and student_org_id:
        selected_student_org = db.query(Organization).filter(
            Organization.id == student_org_id,
            Organization.status == "approved"
        ).first()
        if not selected_student_org:
            return templates.TemplateResponse(
                "auth/register.html",
                _register_context(
                    request,
                    role,
                    form_values,
                    error="Учебный центр не найден",
                    error_field="student_org_id",
                    error_step=5,
                ),
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
            upload = _validate_teacher_document(document)
            os.makedirs("static/documents", exist_ok=True)
            filename = f"{uuid.uuid4().hex}_{upload.safe_filename}"
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
        birth_date=parsed_birth_date if role == "student" else None,
        phone_number=phone_number if role == "student" else None,
        parent_contact_name=parent_contact_name if role == "student" else None,
        parent_contact_phone=parent_contact_phone if role == "student" else None,
        gender=gender if role in ("student", "teacher") else None,
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

    # Студент → добавляем в организацию если выбрана
    if actual_role == UserRole.student and selected_student_org:
        org_student = db.query(OrganizationStudent).filter(
            OrganizationStudent.organization_id == selected_student_org.id,
            OrganizationStudent.student_id == user.id,
        ).first()
        join_status = "accepted" if selected_student_org.is_open else "pending"
        if org_student:
            org_student.status = join_status
            org_student.was_removed_notification = False
        else:
            org_student = OrganizationStudent(
                organization_id=selected_student_org.id,
                student_id=user.id,
                status=join_status,
                was_removed_notification=False,
            )
            db.add(org_student)
        db.commit()

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
    try:
        email = email.strip().lower()
        user = db.query(User).filter(User.email == email).first()
    except Exception as e:
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Ошибка базы данных при поиске пользователя."},
            status_code=500,
        )

    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Неверный email или пароль"},
            status_code=401,
        )

    # Организации, ждущие одобрения, не могут войти
    is_org = getattr(user, "is_org", False)
    is_active = getattr(user, "is_active", True)
    
    if is_org and not is_active:
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Ваш учебный центр ещё не одобрен администратором."},
            status_code=403,
        )

    # Проверяем, заблокирован ли пользователь или ждёт одобрения
    if not is_active:
        user_role = getattr(user, "role", None)
        if user_role == UserRole.teacher_pending:
            error_msg = "Ваша заявка преподавателя всё ещё находится на рассмотрении."
        elif is_org:
            error_msg = "Ваш учебный центр всё ещё находится на рассмотрении."
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

    return RedirectResponse("/dashboard", status_code=302)


# ── Выход ───────────────────────────────────────────────────────────────────

@router.get("/logout")
def logout_get():
    return RedirectResponse(url="/login", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("session")
    return response
