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
from app.utils.group_membership import ACTIVE_GROUP_MEMBER_STATUS
from app.models.review import Review
from app.utils.private_uploads import APPLICATION_ATTACHMENTS, private_upload_destination
from app.utils.uploads import validate_upload_file


APPLICATION_ATTACHMENT_MAX_BYTES = 10 * 1024 * 1024
APPLICATION_ATTACHMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".webp"}


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


def get_organization_students_lists(db: Session, org_id: int) -> tuple[list, list, dict[int, list[dict]]]:
    """Get accepted and pending students for an organization."""
    org_students = db.query(OrganizationStudent).options(
        joinedload(OrganizationStudent.student)
    ).filter(
        OrganizationStudent.organization_id == org_id,
        OrganizationStudent.status.in_(["accepted", "pending"])
    ).order_by(OrganizationStudent.created_at.desc()).all()

    accepted_students = [s for s in org_students if s.status == "accepted"]
    pending_students = [s for s in org_students if s.status == "pending"]
    accepted_student_ids = [s.student_id for s in accepted_students]
    student_groups_by_id: dict[int, list[dict]] = {}
    if accepted_student_ids:
        group_rows = (
            db.query(
                GroupMember.student_id,
                Group.id,
                Group.name,
                GroupMember.grade,
            )
            .join(Group, Group.id == GroupMember.group_id)
            .filter(
                Group.organization_id == org_id,
                GroupMember.student_id.in_(accepted_student_ids),
                GroupMember.status == ACTIVE_GROUP_MEMBER_STATUS,
            )
            .order_by(Group.name.asc())
            .all()
        )
        for student_id, group_id, group_name, grade in group_rows:
            student_groups_by_id.setdefault(student_id, []).append({
                "id": group_id,
                "name": group_name,
                "grade": grade,
            })

    return accepted_students, pending_students, student_groups_by_id


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
            GroupMember.status == ACTIVE_GROUP_MEMBER_STATUS,
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


def invite_organization_teacher(db: Session, org_id: int, teacher_id: int | None, email: str) -> str:
    if teacher_id:
        teacher = db.query(User).filter(
            User.id == teacher_id,
            User.role == UserRole.teacher,
            User.is_active == True,
        ).first()
    else:
        email = email.strip().lower()
        teacher = db.query(User).filter(
            User.email == email,
            User.role == UserRole.teacher,
        ).first()

    if not teacher:
        return "teacher_not_found"

    in_other_org = db.query(OrganizationTeacher).filter(
        OrganizationTeacher.teacher_id == teacher.id,
        OrganizationTeacher.status == "accepted",
        OrganizationTeacher.organization_id != org_id,
    ).first()
    if in_other_org:
        return "in_other_org"

    existing = db.query(OrganizationTeacher).filter(
        OrganizationTeacher.organization_id == org_id,
        OrganizationTeacher.teacher_id == teacher.id
    ).first()

    if existing:
        return "already_invited"

    org_teacher = OrganizationTeacher(
        organization_id=org_id,
        teacher_id=teacher.id,
        status="pending"
    )
    db.add(org_teacher)
    db.commit()
    return "success"


def accept_incoming_teacher_service(db: Session, org_id: int, link_id: int):
    org_teacher = db.query(OrganizationTeacher).filter(
        OrganizationTeacher.id == link_id,
        OrganizationTeacher.organization_id == org_id,
        OrganizationTeacher.status == "pending"
    ).first()
    
    if not org_teacher:
        raise ValueError("Заявка не найдена")

    teacher = db.query(User).filter(User.id == org_teacher.teacher_id).first()
    if not teacher:
        raise ValueError("Преподаватель не найден")

    try:
        org_teacher.status = "accepted"
        org_teacher.was_accepted_notification = True
        teacher.is_active = True
        teacher.role = UserRole.teacher
        db.commit()
        db.refresh(teacher)
        db.refresh(org_teacher)
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Ошибка сервера при принятии заявки: {str(e)}")


def reject_incoming_teacher_service(db: Session, org_id: int, link_id: int):
    link = db.query(OrganizationTeacher).filter(
        OrganizationTeacher.id == link_id,
        OrganizationTeacher.organization_id == org_id,
        OrganizationTeacher.status == "pending"
    ).first()

    if not link:
        raise ValueError("Заявка не найдена")

    try:
        link.status = "rejected"
        db.commit()
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Ошибка при отклонении заявки: {str(e)}")


def remove_teacher_from_organization(db: Session, org_id: int, teacher_id: int):
    link = db.query(OrganizationTeacher).filter(
        OrganizationTeacher.organization_id == org_id,
        OrganizationTeacher.teacher_id == teacher_id
    ).first()
    if link:
        db.delete(link)
        db.commit()


def accept_student_in_organization(db: Session, org_id: int, link_id: int):
    link = db.query(OrganizationStudent).filter(
        OrganizationStudent.id == link_id,
        OrganizationStudent.organization_id == org_id,
        OrganizationStudent.status == "pending"
    ).first()
    if link:
        link.status = "accepted"
        db.commit()


def reject_student_in_organization(db: Session, org_id: int, link_id: int):
    link = db.query(OrganizationStudent).filter(
        OrganizationStudent.id == link_id,
        OrganizationStudent.organization_id == org_id,
        OrganizationStudent.status == "pending"
    ).first()
    if link:
        link.status = "rejected"
        link.was_removed_notification = False
        db.commit()


def remove_student_from_organization(db: Session, org_id: int, student_id: int):
    link = db.query(OrganizationStudent).filter(
        OrganizationStudent.organization_id == org_id,
        OrganizationStudent.student_id == student_id,
        OrganizationStudent.status.in_(["accepted", "pending"])
    ).first()
    if link:
        link.status = "removed"
        link.was_removed_notification = True
        db.commit()


def teacher_accepts_invite(db: Session, teacher_id: int, invite_id: int):
    invite = db.query(OrganizationTeacher).filter(
        OrganizationTeacher.id == invite_id,
        OrganizationTeacher.teacher_id == teacher_id
    ).first()
    if invite:
        invite.status = "accepted"
        invite.was_accepted_notification = True
        db.commit()


def teacher_rejects_invite(db: Session, teacher_id: int, invite_id: int):
    invite = db.query(OrganizationTeacher).filter(
        OrganizationTeacher.id == invite_id,
        OrganizationTeacher.teacher_id == teacher_id
    ).first()
    if invite:
        invite.status = "rejected"
        db.commit()


def student_join_organization_service(db: Session, org_id: int, user: User, force: bool) -> tuple[str, str | None, bool | None]:
    org = db.query(Organization).filter(
        Organization.id == org_id,
        Organization.status == "approved"
    ).first()
    if not org:
        raise ValueError("Организация не найдена")

    existing_this_org = db.query(OrganizationStudent).filter(
        OrganizationStudent.organization_id == org.id,
        OrganizationStudent.student_id == user.id,
    ).first()

    if existing_this_org and existing_this_org.status in ("accepted", "pending"):
        return "already_in_this_org", None, None

    other_org_link = db.query(OrganizationStudent).filter(
        OrganizationStudent.student_id == user.id,
        OrganizationStudent.organization_id != org.id,
        OrganizationStudent.status.in_(["accepted", "pending"])
    ).first()
    
    if other_org_link:
        if not force:
            old_org = db.query(Organization).filter(Organization.id == other_org_link.organization_id).first()
            return "in_other_org", (old_org.name if old_org else "Неизвестно"), None
        else:
            other_org_link.status = "removed"
            other_org_link.was_removed_notification = False

    new_status = "accepted" if org.is_open else "pending"

    if existing_this_org:
        existing_this_org.status = new_status
        existing_this_org.was_removed_notification = False
    else:
        existing_this_org = OrganizationStudent(
            organization_id=org.id,
            student_id=user.id,
            status=new_status,
            was_removed_notification=False,
        )
        db.add(existing_this_org)

    db.commit()
    return "success", None, org.is_open


def student_leave_organization_service(db: Session, user_id: int):
    link = db.query(OrganizationStudent).filter(
        OrganizationStudent.student_id == user_id,
        OrganizationStudent.status.in_(["accepted", "pending"])
    ).first()

    if link:
        link.status = "left"
        link.was_removed_notification = False
        db.commit()


def update_organization_profile_service(
    db: Session, org_id: int, name: str, description: str, phone: str, website: str | None, is_open: str
):
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise ValueError("Организация не найдена")
        
    org.name = name
    org.description = description
    org.phone = phone
    org.website = website
    org.is_open = is_open.lower() == "true"
    db.commit()


def teacher_apply_organization_service(
    db: Session, org_id: int, user: User, cover_letter: str | None, attachment
) -> tuple[str, str | None]:
    org = db.query(Organization).filter(Organization.id == org_id, Organization.status == "approved").first()
    if not org:
        raise ValueError("Организация не найдена")

    in_other_org = db.query(OrganizationTeacher).filter(
        OrganizationTeacher.teacher_id == user.id,
        OrganizationTeacher.status == "accepted",
        OrganizationTeacher.organization_id != org.id
    ).first()
    if in_other_org:
        return "in_other_org", None

    existing = db.query(OrganizationTeacher).filter(
        OrganizationTeacher.organization_id == org.id,
        OrganizationTeacher.teacher_id == user.id
    ).first()
    if existing:
        return "already_exists", existing.status

    attachment_path = None
    if attachment and getattr(attachment, "filename", None):
        import uuid, shutil
        
        upload = validate_upload_file(
            attachment,
            allowed_extensions=APPLICATION_ATTACHMENT_EXTENSIONS,
            max_bytes=APPLICATION_ATTACHMENT_MAX_BYTES,
            invalid_type_message="Недопустимый тип файла вложения",
        )
        safe_name = f"{uuid.uuid4().hex}_{upload.safe_filename}"
        attachment_path, dest = private_upload_destination(APPLICATION_ATTACHMENTS, safe_name)
        with open(dest, "wb") as f:
            shutil.copyfileobj(attachment.file, f)

    try:
        org_teacher = OrganizationTeacher(
            organization_id=org.id,
            teacher_id=user.id,
            status="pending",
            cover_letter=cover_letter.strip() if cover_letter else None,
            attachment=attachment_path,
        )
        db.add(org_teacher)
        db.commit()
    except Exception as e:
        db.rollback()
        raise RuntimeError("Ошибка при создании заявки")

    return "success", None
