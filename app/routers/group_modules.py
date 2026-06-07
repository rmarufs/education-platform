from typing import Optional
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.group_service import get_manageable_group
from app.services.group_module_service import (
    create_group_module,
    edit_group_module,
    delete_group_module,
)

router = APIRouter()

@router.post("/{group_id:int}/modules/create")
def group_module_create(
    group_id: int,
    request: Request,
    title: str = Form(...),
    order_index: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    try:
        from app.deps.auth import get_user
        user = get_user(request, db)
        if not user:
            raise HTTPException(status_code=401, detail="Необходима авторизация")
        _, group = get_manageable_group(db, group_id, user)
    except ValueError as e:
        status_code = 404 if "не найдена" in str(e).lower() else 403
        raise HTTPException(status_code=status_code, detail=str(e))

    try:
        create_group_module(db, group, title, order_index)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return RedirectResponse(f"/groups/{group_id}/manage?success=module_created", status_code=302)

@router.post("/{group_id:int}/modules/{module_id:int}/edit")
def group_module_edit(
    group_id: int,
    module_id: int,
    request: Request,
    title: str = Form(...),
    order_index: int = Form(0),
    db: Session = Depends(get_db),
):
    try:
        from app.deps.auth import get_user
        user = get_user(request, db)
        if not user:
            raise HTTPException(status_code=401, detail="Необходима авторизация")
        _, group = get_manageable_group(db, group_id, user)
    except ValueError as e:
        status_code = 404 if "не найдена" in str(e).lower() else 403
        raise HTTPException(status_code=status_code, detail=str(e))

    try:
        edit_group_module(db, group, module_id, title, order_index)
    except ValueError as e:
        status_code = 404 if "не найден" in str(e).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(e))

    return RedirectResponse(f"/groups/{group_id}/manage?success=module_saved", status_code=302)

@router.post("/{group_id:int}/modules/{module_id:int}/delete")
def group_module_delete(
    group_id: int,
    module_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        from app.deps.auth import get_user
        user = get_user(request, db)
        if not user:
            raise HTTPException(status_code=401, detail="Необходима авторизация")
        _, group = get_manageable_group(db, group_id, user)
    except ValueError as e:
        status_code = 404 if "не найдена" in str(e).lower() else 403
        raise HTTPException(status_code=status_code, detail=str(e))

    try:
        delete_group_module(db, group, module_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return RedirectResponse(f"/groups/{group_id}/manage?success=module_deleted", status_code=302)
