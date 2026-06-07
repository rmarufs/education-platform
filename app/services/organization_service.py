"""Organization read-only service logic."""

from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import func

from app.models.user import User, UserRole
from app.models.organization import (
    Organization,
    OrganizationTeacher,
    OrganizationStudent,
)
from app.models.course import Course
from app.models.group import Group, GroupMember
from app.models.review import Review


def get_approved_organizations_list(db: Session) -> list[dict]:
    """Retrieve all approved organizations for API listing."""
    orgs = (
        db.query(Organization)
        .options(joinedload(Organization.user))
        .filter(Organization.status == "approved")
        .order_by(Organization.name)
        .all()
    )
    return [
        {
            "id": o.id,
            "name": o.name,
            "logo_url": o.logo_url or (o.user.avatar_url if o.user else None),
            "is_open": o.is_open,
        }
        for o in orgs
    ]


def search_teachers_for_organization(db: Session, q: str, org: Organization | None) -> list[dict]:
    """Search teachers and determine invitation status for a specific organization."""
    query = db.query(User).filter(
        User.role == UserRole.teacher,
        User.is_active == True,
    )
    if q.strip():
        query = query.filter(User.name.ilike(f"%{q.strip()}%"))

    teachers = query.order_by(User.name).limit(20).all()

    teacher_ids = [t.id for t in teachers]
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

    already_invited = set()
    if org and teacher_ids:
        inv_links = db.query(OrganizationTeacher).filter(
            OrganizationTeacher.organization_id == org.id,
            OrganizationTeacher.teacher_id.in_(teacher_ids),
        ).all()
        already_invited = {l.teacher_id for l in inv_links}

    result = []
    for t in teachers:
        org_link = org_map.get(t.id)
        result.append({
            "id": t.id,
            "name": t.name,
            "bio": (t.bio[:120] if t.bio else None),
            "avatar": getattr(t, "avatar_url", None),
            "org_name": org_link.organization.name if org_link else None,
            "org_id": org_link.organization_id if org_link else None,
            "already_invited": t.id in already_invited,
        })
    return result


def get_organization_dashboard_stats(db: Session, org_id: int) -> dict:
    """Calculate statistics for the organization dashboard."""
    accepted_count = db.query(OrganizationTeacher).filter(
        OrganizationTeacher.organization_id == org_id,
        OrganizationTeacher.status == "accepted"
    ).count()

    teacher_ids = [teacher_id for (teacher_id,) in db.query(OrganizationTeacher.teacher_id).filter(
        OrganizationTeacher.organization_id == org_id,
        OrganizationTeacher.status == "accepted"
    ).all()]

    courses_count = db.query(Course).filter(Course.teacher_id.in_(teacher_ids)).count() if teacher_ids else 0

    incoming_count = db.query(OrganizationTeacher).filter(
        OrganizationTeacher.organization_id == org_id,
        OrganizationTeacher.status == "pending"
    ).count()

    student_requests_count = db.query(OrganizationStudent).filter(
        OrganizationStudent.organization_id == org_id,
        OrganizationStudent.status == "pending"
    ).count()

    students_count = db.query(OrganizationStudent).filter(
        OrganizationStudent.organization_id == org_id,
        OrganizationStudent.status == "accepted"
    ).count()

    groups_count = db.query(Group).filter(Group.organization_id == org_id).count()

    return {
        "teachers_count": accepted_count,
        "courses_count": courses_count,
        "students_count": students_count,
        "incoming_count": incoming_count,
        "student_requests_count": student_requests_count,
        "groups_count": groups_count,
    }


def get_organization_teachers_lists(db: Session, org_id: int) -> tuple[list, list, list]:
    """Get accepted, pending, and rejected teachers for an organization."""
    all_links = db.query(OrganizationTeacher).options(joinedload(OrganizationTeacher.teacher)).filter(
        OrganizationTeacher.organization_id == org_id
    ).all()

    accepted = [l for l in all_links if l.status == "accepted"]
    pending  = [l for l in all_links if l.status == "pending"]
    rejected = [l for l in all_links if l.status == "rejected"]
    return accepted, pending, rejected


def get_organization_students_lists(db: Session, org_id: int) -> tuple[list, list]:
    """Get accepted and pending students for an organization."""
    org_students = db.query(OrganizationStudent).options(
        joinedload(OrganizationStudent.student)
    ).filter(
        OrganizationStudent.organization_id == org_id,
        OrganizationStudent.status.in_(["accepted", "pending"])
    ).order_by(OrganizationStudent.created_at.desc()).all()

    accepted_students = [s for s in org_students if s.status == "accepted"]
    pending_students = [s for s in org_students if s.status == "pending"]
    return accepted_students, pending_students


def get_organization_teacher_courses(db: Session, org_id: int, teacher_id: int) -> tuple[User | None, list[Course]]:
    """Get teacher and their courses if they belong to the organization."""
    membership = db.query(OrganizationTeacher).filter(
        OrganizationTeacher.organization_id == org_id,
        OrganizationTeacher.teacher_id == teacher_id,
        OrganizationTeacher.status == "accepted"
    ).first()
    
    if not membership:
        raise ValueError("Этот преподаватель не является членом вашего учебного центра")

    teacher = db.query(User).filter(User.id == teacher_id).first()
    if not teacher:
        raise ValueError("Преподаватель не найден")

    courses = db.query(Course).options(
        joinedload(Course.category)
    ).filter(Course.teacher_id == teacher_id).order_by(Course.created_at.desc()).all()
    
    return teacher, courses


def get_public_organization_profile_data(db: Session, org_id: int, user: User | None) -> dict:
    """Gather all required data for the public organization profile."""
    org = (
        db.query(Organization)
        .options(joinedload(Organization.user))
        .filter(Organization.id == org_id)
        .first()
    )
    if not org:
        raise ValueError("Организация не найдена")
    if org.status != "approved" and not (user and (user.is_admin or org.user_id == user.id)):
        raise ValueError("Организация не найдена")

    org_teachers = db.query(OrganizationTeacher).options(joinedload(OrganizationTeacher.teacher)).filter(
        OrganizationTeacher.organization_id == org.id,
        OrganizationTeacher.status == "accepted"
    ).all()
    teacher_ids = [ot.teacher_id for ot in org_teachers]

    courses = []
    if teacher_ids:
        courses = db.query(Course).options(
            joinedload(Course.teacher),
            joinedload(Course.category)
        ).filter(Course.teacher_id.in_(teacher_ids)).all()

    direct_student_ids = {
        student_id
        for (student_id,) in db.query(OrganizationStudent.student_id)
        .join(User, User.id == OrganizationStudent.student_id)
        .filter(
            OrganizationStudent.organization_id == org.id,
            OrganizationStudent.status == "accepted",
            User.role == UserRole.student,
        )
        .all()
    }
    
    group_student_ids = {
        student_id
        for (student_id,) in db.query(GroupMember.student_id)
        .join(Group, Group.id == GroupMember.group_id)
        .join(User, User.id == GroupMember.student_id)
        .filter(
            Group.organization_id == org.id,
            User.role == UserRole.student,
        )
        .all()
    }
    students_count = len(direct_student_ids | group_student_ids)

    avg_rating = 0.0
    if teacher_ids:
        avg = db.query(func.avg(Review.rating)).filter(Review.teacher_id.in_(teacher_ids)).scalar()
        avg_rating = round(avg or 0.0, 1)

    user_application = None
    user_in_any_org = False
    user_student_membership = None
    current_student_org = None

    if user and user.is_teacher:
        user_application = db.query(OrganizationTeacher).filter(
            OrganizationTeacher.organization_id == org.id,
            OrganizationTeacher.teacher_id == user.id
        ).first()
        user_in_any_org = db.query(OrganizationTeacher).filter(
            OrganizationTeacher.teacher_id == user.id,
            OrganizationTeacher.status == "accepted"
        ).first() is not None

    if user and user.is_student:
        user_student_membership = db.query(OrganizationStudent).filter(
            OrganizationStudent.organization_id == org.id,
            OrganizationStudent.student_id == user.id,
            OrganizationStudent.status.in_(["accepted", "pending", "rejected"])
        ).first()
        
        if not user_student_membership:
            other_membership = db.query(OrganizationStudent).filter(
                OrganizationStudent.student_id == user.id,
                OrganizationStudent.status.in_(["accepted", "pending"])
            ).first()
            if other_membership:
                current_student_org = db.query(Organization).filter(
                    Organization.id == other_membership.organization_id
                ).first()

    return {
        "org": org,
        "org_teachers": [ot.teacher for ot in org_teachers],
        "courses": courses,
        "students_count": students_count,
        "avg_rating": avg_rating,
        "user_application": user_application,
        "user_in_any_org": user_in_any_org,
        "user_student_membership": user_student_membership,
        "current_student_org": current_student_org,
    }
