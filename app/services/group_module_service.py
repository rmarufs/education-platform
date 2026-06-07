from typing import Optional
from sqlalchemy.orm import Session
from app.models.group import Group, GroupModule, GroupLesson

def create_group_module(db: Session, group: Group, title: str, order_index: Optional[int]) -> GroupModule:
    clean_title = title.strip()
    if not clean_title:
        raise ValueError("Введите название модуля")

    module_order = order_index
    if module_order is None:
        module_order = db.query(GroupModule).filter(GroupModule.group_id == group.id).count()

    module = GroupModule(
        group_id=group.id,
        title=clean_title,
        order_index=module_order,
    )
    db.add(module)
    db.commit()
    return module

def edit_group_module(db: Session, group: Group, module_id: int, title: str, order_index: int):
    module = db.query(GroupModule).filter(
        GroupModule.id == module_id,
        GroupModule.group_id == group.id,
    ).first()
    if not module:
        raise ValueError("Модуль не найден")

    clean_title = title.strip()
    if not clean_title:
        raise ValueError("Введите название модуля")

    module.title = clean_title
    module.order_index = order_index
    db.commit()

def delete_group_module(db: Session, group: Group, module_id: int):
    module = db.query(GroupModule).filter(
        GroupModule.id == module_id,
        GroupModule.group_id == group.id,
    ).first()
    if not module:
        raise ValueError("Модуль не найден")

    db.query(GroupLesson).filter(
        GroupLesson.group_id == group.id,
        GroupLesson.group_module_id == module.id,
    ).update({GroupLesson.group_module_id: None}, synchronize_session=False)
    db.delete(module)
    db.commit()
