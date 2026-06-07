"""Announcement service logic for organizations."""

from datetime import datetime
import logging
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.organization import (
    Organization,
    OrganizationAnnouncement,
    OrganizationAnnouncementDismissal,
    OrganizationTeacher,
    OrganizationStudent,
)
from app.utils.announcements import VALID_AUDIENCES, get_visible_announcement
from app.utils.datetime_helpers import parse_optional_datetime

logger = logging.getLogger(__name__)


def get_organization_announcements(db: Session, org_id: int) -> list[OrganizationAnnouncement]:
    """Retrieve all announcements for a specific organization."""
    return db.query(OrganizationAnnouncement).filter(
        OrganizationAnnouncement.organization_id == org_id
    ).order_by(OrganizationAnnouncement.created_at.desc()).all()


def get_owned_announcement_or_raise(db: Session, org_id: int, announcement_id: int) -> OrganizationAnnouncement:
    """Retrieve an announcement owned by the organization or raise ValueError."""
    announcement = db.query(OrganizationAnnouncement).filter(
        OrganizationAnnouncement.id == announcement_id,
        OrganizationAnnouncement.organization_id == org_id,
    ).first()
    if not announcement:
        raise ValueError("Announcement not found")
    return announcement


def create_organization_announcement_service(
    db: Session, org: Organization, user: User, title: str, body: str, audience: str, expires_at: str | None
) -> OrganizationAnnouncement:
    """Create a new announcement and send push notifications."""
    if audience not in VALID_AUDIENCES:
        raise ValueError("Invalid audience")
        
    title = title.strip()
    body = body.strip()
    if not title or not body:
        raise ValueError("Title and body are required")

    announcement = OrganizationAnnouncement(
        organization_id=org.id,
        title=title,
        body=body,
        audience=audience,
        created_by_id=user.id,
        expires_at=parse_optional_datetime(expires_at),
    )
    db.add(announcement)
    db.commit()

    # Send push notifications
    try:
        from app.utils.push import send_push_to_users
        target_user_ids = []
        if audience in ("all", "teachers"):
            teachers = db.query(OrganizationTeacher).filter(
                OrganizationTeacher.organization_id == org.id,
                OrganizationTeacher.status == "accepted"
            ).all()
            target_user_ids.extend([t.teacher_id for t in teachers])
            
        if audience in ("all", "students"):
            students = db.query(OrganizationStudent).filter(
                OrganizationStudent.organization_id == org.id,
                OrganizationStudent.status == "accepted"
            ).all()
            target_user_ids.extend([s.student_id for s in students])
            
        if target_user_ids:
            send_push_to_users(
                db=db,
                user_ids=target_user_ids,
                title="Новое объявление",
                body=org.name or announcement.title,
                target_url=f"/dashboard?announcement_id={announcement.id}",
                notification_type="organization_announcement",
                entity_id=announcement.id
            )
    except Exception as e:
        logger.error(f"Error sending push for announcement: {e}")

    return announcement


def update_organization_announcement_service(
    db: Session, org_id: int, announcement_id: int, title: str, body: str, audience: str, expires_at: str | None
) -> OrganizationAnnouncement:
    """Update an existing organization announcement."""
    if audience not in VALID_AUDIENCES:
        raise ValueError("Invalid audience")
        
    clean_title = title.strip()
    clean_body = body.strip()
    if not clean_title or not clean_body:
        raise ValueError("Title and body are required")

    announcement = get_owned_announcement_or_raise(db, org_id, announcement_id)
    announcement.title = clean_title
    announcement.body = clean_body
    announcement.audience = audience
    announcement.expires_at = parse_optional_datetime(expires_at)
    announcement.updated_at = datetime.utcnow()
    db.commit()
    return announcement


def toggle_organization_announcement_service(db: Session, org_id: int, announcement_id: int) -> OrganizationAnnouncement:
    """Toggle the active status of an announcement."""
    announcement = get_owned_announcement_or_raise(db, org_id, announcement_id)
    announcement.is_active = not announcement.is_active
    announcement.updated_at = datetime.utcnow()
    db.commit()
    return announcement


def delete_organization_announcement_service(db: Session, org_id: int, announcement_id: int) -> None:
    """Delete an organization announcement."""
    announcement = get_owned_announcement_or_raise(db, org_id, announcement_id)
    db.delete(announcement)
    db.commit()


def dismiss_organization_announcement_service(db: Session, user: User, announcement_id: int) -> None:
    """Dismiss an announcement for a specific user."""
    announcement = get_visible_announcement(db, user, announcement_id)
    if not announcement:
        raise ValueError("Announcement is not available")

    existing = db.query(OrganizationAnnouncementDismissal).filter(
        OrganizationAnnouncementDismissal.announcement_id == announcement.id,
        OrganizationAnnouncementDismissal.user_id == user.id,
    ).first()
    
    if not existing:
        db.add(OrganizationAnnouncementDismissal(
            announcement_id=announcement.id,
            user_id=user.id,
        ))
        db.commit()
