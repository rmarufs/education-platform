"""Search logic service."""

import logging
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.user import User, UserRole
from app.models.course import Course
from app.models.organization import Organization, OrganizationTeacher, OrganizationStudent
from app.utils.text import plain_text

logger = logging.getLogger("search_api")


def perform_search(
    db: Session,
    user: User | None,
    q: str,
    category_id: int,
    level: str,
    sort: str,
    page: int,
    per_page: int,
) -> dict:
    user_is_student = bool(user and user.is_student)
    user_org_id = None
    if user_is_student:
        student_org_link = db.query(OrganizationStudent).filter(OrganizationStudent.student_id == user.id).first()
        if student_org_link:
            user_org_id = student_org_link.organization_id

    query = db.query(Course).options(
        joinedload(Course.teacher)
            .selectinload(User.employer_organizations)
            .joinedload(OrganizationTeacher.organization),
        joinedload(Course.category),
        selectinload(Course.modules),
    )

    if q:
        query = query.filter(
            (Course.title.ilike(f"%{q}%")) | (Course.description.ilike(f"%{q}%"))
        )
    if category_id:
        query = query.filter(Course.category_id == category_id)
    if level:
        query = query.filter(Course.level == level)

    # Сортировка
    if sort == "newest":
        query = query.order_by(Course.created_at.desc())
    elif sort == "oldest":
        query = query.order_by(Course.created_at.asc())
    else:
        query = query.order_by(Course.rating.desc())

    total = query.count()
    courses = query.offset((page - 1) * per_page).limit(per_page).all()

    organizations = []
    
    # Поиск организаций: если запрос пуст, показываем популярные (например, первые 3 одобренные)
    org_query = db.query(Organization).options(joinedload(Organization.user)).filter(Organization.status == "approved")
    if q:
        org_query = org_query.filter(Organization.name.ilike(f"%{q}%"))
        orgs = org_query.limit(10).all()
    else:
        orgs = org_query.limit(3).all()

    organizations = [
        {
            "id": o.id,
            "name": o.name,
            "description": plain_text(o.description)[:120] if o.description else "Организация",
            "logo_url": o.logo_url or (o.user.avatar_url if o.user else None)
        }
        for o in orgs
    ]

    # Поиск преподавателей
    teachers_result = []
    if q:
        found_teachers = (
            db.query(User)
            .filter(
                User.role == UserRole.teacher,
                User.is_active == True,
                User.name.ilike(f"%{q}%"),
            )
            .limit(8)
            .all()
        )
        teacher_ids = [t.id for t in found_teachers]
        org_map = {}
        if teacher_ids:
            links = (
                db.query(OrganizationTeacher)
                .options(joinedload(OrganizationTeacher.organization))
                .filter(
                    OrganizationTeacher.teacher_id.in_(teacher_ids),
                    OrganizationTeacher.status == "accepted",
                )
                .all()
            )
            for link in links:
                org_map[link.teacher_id] = link
        for t in found_teachers:
            org_link = org_map.get(t.id)
            teachers_result.append({
                "id": t.id,
                "name": t.name,
                "bio": (t.bio[:100] if t.bio else None),
                "avatar": getattr(t, "avatar_url", None),
                "org_name": org_link.organization.name if org_link else None,
                "org_id": org_link.organization_id if org_link else None,
            })

    logger.info(f"Search query: q='{q}', category_id={category_id}, level='{level}', sort='{sort}', user_is_student={user_is_student}")
    logger.info(f"Results found: courses={total}, organizations={len(organizations)}, teachers={len(teachers_result)}")

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "courses": [
            {
                "id": c.id,
                "title": c.title,
                "description": plain_text(c.description)[:120],
                "image": c.image,
                "teacher_name": c.teacher.name,
                "rating": c.rating,
                "level": c.level,
                "category": c.category.name if c.category else None,
                "created_at": c.created_at.strftime("%d.%m.%Y"),
                "modules_count": len(c.modules) if c.modules else 0,
                "teacher_orgs": [{"id": ot.organization_id, "name": ot.organization.name} for ot in c.teacher.employer_organizations if ot.status == 'accepted'] if hasattr(c.teacher, 'employer_organizations') else []
            }
            for c in courses
        ],
        "organizations": organizations,
        "teachers": teachers_result,
        "user_is_student": user_is_student,
        "user_org_id": user_org_id,
    }
