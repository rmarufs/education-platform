from typing import Optional, List
from fastapi import APIRouter, Depends, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.ui import templates
from app.utils.announcements import get_visible_announcements
from app.utils.image import upload_group_cover_image
from app.utils.upload_constants import IMAGE_EXTENSIONS as GROUP_LESSON_COVER_EXTENSIONS, COVER_IMAGE_MAX_BYTES as GROUP_LESSON_COVER_MAX_BYTES
from app.utils.uploads import validate_upload_file

from app.deps.auth import get_user as _get_user
from app.models.organization import Organization

def _require_org(request: Request, db: Session):
    user = _get_user(request, db)
    if not user or not user.is_org:
        return None, RedirectResponse("/login", status_code=302)
    org = db.query(Organization).filter(Organization.user_id == user.id).first()
    if not org:
        return None, RedirectResponse("/", status_code=302)
    return (user, org), None

def _require_teacher(request: Request, db: Session):
    user = _get_user(request, db)
    if not user or not user.is_teacher:
        return None, RedirectResponse("/login", status_code=302)
    return user, None
from app.services.group_service import (
    get_org_for_group, get_manageable_group, get_organization_groups, get_teacher_groups,
    create_group, update_group, delete_group, assign_teacher, add_student_to_group,
    bulk_add_students_to_group, remove_student_from_group, update_group_avatar
)

router = APIRouter()

class BulkAddStudentsPayload(BaseModel):
    student_ids: List[int]
    grade: Optional[int] = None

@router.get("/", response_class=HTMLResponse)
def groups_list(request: Request, db: Session = Depends(get_db)):
    result, redirect = _require_org(request, db)
    if redirect:
        return redirect
    user, org = result

    groups, teachers = get_organization_groups(db, org.id)
    return templates.TemplateResponse("groups/list.html", {
        "request": request,
        "user": user,
        "org": org,
        "groups": groups,
        "teachers": teachers,
    })

@router.get("/my", response_class=HTMLResponse)
def my_groups(request: Request, db: Session = Depends(get_db)):
    user, redirect = _require_teacher(request, db)
    if redirect:
        return redirect

    groups = get_teacher_groups(db, user.id)
    return templates.TemplateResponse("groups/my_groups.html", {
        "request": request,
        "user": user,
        "groups": groups,
        "visible_announcements": get_visible_announcements(db, user, limit=3),
    })

@router.post("/create")
def group_create(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    teacher_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    result, redirect = _require_org(request, db)
    if redirect:
        return redirect
    user, org = result

    group = create_group(db, org, name, description, teacher_id)
    return RedirectResponse(f"/groups/{group.id}/manage", status_code=302)

@router.get("/{group_id:int}", response_class=HTMLResponse)
def group_detail(group_id: int, request: Request, db: Session = Depends(get_db)):
    result, redirect = _require_org(request, db)
    if redirect:
        return redirect
    user, org = result
    try:
        get_org_for_group(db, group_id, user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return RedirectResponse(f"/groups/{group_id}/manage", status_code=302)

@router.post("/{group_id:int}/edit")
def group_edit(
    group_id: int,
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    is_active: str = Form("true"),
    db: Session = Depends(get_db),
):
    result, redirect = _require_org(request, db)
    if redirect:
        return redirect
    user, org = result
    try:
        update_group(db, org, group_id, name, description, is_active.lower() == "true")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return RedirectResponse(f"/groups/{group_id}/manage?success=saved", status_code=302)

@router.post("/{group_id:int}/avatar")
def group_avatar(group_id: int, request: Request, avatar: UploadFile = File(...), db: Session = Depends(get_db)):
    from app.deps.auth import get_user
    user = get_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Необходима авторизация")

    try:
        _, group = get_manageable_group(db, group_id, user)
    except ValueError as e:
        status_code = 404 if "не найдена" in str(e).lower() else 403
        raise HTTPException(status_code=status_code, detail=str(e))

    if not avatar or not avatar.filename:
        return RedirectResponse(f"/groups/{group_id}/manage", status_code=302)

    try:
        validate_upload_file(
            avatar,
            allowed_extensions=GROUP_LESSON_COVER_EXTENSIONS,
            max_bytes=GROUP_LESSON_COVER_MAX_BYTES,
            invalid_type_message="Разрешены только JPG, JPEG, PNG и WEBP",
            too_large_message="Изображение должно быть не больше 5MB",
        )
    except HTTPException:
        return RedirectResponse(f"/groups/{group_id}/manage?error=invalid_image", status_code=302)

    avatar_url = upload_group_cover_image(
        avatar.file,
        public_id=f"groups/group_{group.id}"
    )
    if avatar_url:
        update_group_avatar(db, group, avatar_url)
    return RedirectResponse(f"/groups/{group_id}/manage?success=avatar", status_code=302)

@router.post("/{group_id:int}/delete")
def group_delete(group_id: int, request: Request, db: Session = Depends(get_db)):
    result, redirect = _require_org(request, db)
    if redirect:
        return redirect
    user, org = result
    try:
        delete_group(db, org, group_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return RedirectResponse("/groups/", status_code=302)

@router.post("/{group_id:int}/assign-teacher")
def group_assign_teacher(
    group_id: int,
    request: Request,
    teacher_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    result, redirect = _require_org(request, db)
    if redirect:
        return redirect
    user, org = result
    try:
        assign_teacher(db, org, group_id, teacher_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return RedirectResponse(f"/groups/{group_id}/manage?success=teacher", status_code=302)

@router.post("/{group_id:int}/add-student")
def group_add_student(
    group_id: int,
    request: Request,
    student_id: int = Form(...),
    grade: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    result, redirect = _require_org(request, db)
    if redirect:
        return redirect
    user, org = result
    
    try:
        added = add_student_to_group(db, org, group_id, student_id, grade)
        if not added:
            return RedirectResponse(
                f"/groups/{group_id}/manage?error=not_org_member", status_code=302
            )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return RedirectResponse(f"/groups/{group_id}/manage?success=student_added", status_code=302)

@router.post("/{group_id:int}/students/bulk-add")
def group_bulk_add_students(
    group_id: int,
    payload: BulkAddStudentsPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    result, redirect = _require_org(request, db)
    if redirect:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user, org = result
    
    try:
        added_count, skipped_count = bulk_add_students_to_group(db, org, group_id, payload.student_ids, payload.grade)
    except ValueError as e:
        status_code = 400 if "ученики" in str(e).lower() else 404
        raise HTTPException(status_code=status_code, detail=str(e))
        
    return {
        "success": True,
        "added_count": added_count,
        "skipped_count": skipped_count,
    }

@router.post("/{group_id:int}/remove-student/{student_id:int}")
def group_remove_student(
    group_id: int,
    student_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    result, redirect = _require_org(request, db)
    if redirect:
        return redirect
    user, org = result
    
    try:
        remove_student_from_group(db, org, group_id, student_id, removed_by_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return RedirectResponse(f"/groups/{group_id}/manage", status_code=302)
