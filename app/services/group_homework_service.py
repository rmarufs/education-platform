from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session, joinedload, selectinload
from app.models.group import (
    Group, GroupMember, GroupLesson, GroupHomework, 
    GroupHomeworkSubmission, GroupHomeworkNotification,
)
from app.utils.datetime_helpers import parse_homework_deadline as _parse_homework_deadline
import logging
logger = logging.getLogger(__name__)

def save_homework_record(
    db: Session, group: Group, lesson: GroupLesson, user_id: int,
    clean_title: str, clean_description: str, deadline_is_enabled: bool, deadline: str | None,
    material_file_url: str | None, material_file_type: str | None, material_filename: str | None,
    material_url: str | None, material_url_type: str | None, material_url_filename: str | None,
):
    homework = lesson.homework
    is_new_homework = homework is None
    if not homework:
        homework = GroupHomework(
            group_id=group.id,
            lesson_id=lesson.id,
            created_by_id=user_id,
            description=clean_description,
        )
        db.add(homework)

    homework.title = clean_title
    homework.description = clean_description
    homework.deadline = _parse_homework_deadline(deadline) if deadline_is_enabled else None

    if material_file_url:
        homework.material_url = material_file_url
        homework.material_type = material_file_type
        homework.material_filename = material_filename
    elif material_url:
        homework.material_url = material_url
        homework.material_type = material_url_type
        homework.material_filename = material_url_filename

    db.commit()
    
    if is_new_homework:
        try:
            student_ids = [
                student_id for (student_id,) in db.query(GroupMember.student_id)
                .filter(GroupMember.group_id == group.id)
                .all()
            ]
            notifications_created = []
            for student_id in student_ids:
                notif = GroupHomeworkNotification(
                    homework_id=homework.id,
                    student_id=student_id,
                    notification_type="new_homework",
                )
                db.add(notif)
                notifications_created.append(notif)
            db.commit()

            try:
                from app.utils.push import send_push_to_user
                for notif in notifications_created:
                    send_push_to_user(
                        db=db,
                        user_id=notif.student_id,
                        title="Новое домашнее задание",
                        body=homework.title,
                        target_url=f"/dashboard/student/homework-notifications/{notif.id}/open",
                        notification_type="new_homework",
                        entity_id=notif.id
                    )
            except Exception as e:
                logger.error(f"Error sending push for new homework: {e}")
        except Exception as outer_e:
            logger.error(f"Error creating homework notifications: {outer_e}")
            db.rollback()

def delete_homework_record(db: Session, group_id: int, lesson_id: int):
    homework = db.query(GroupHomework).filter(
        GroupHomework.group_id == group_id,
        GroupHomework.lesson_id == lesson_id,
    ).first()
    if homework:
        db.query(GroupHomeworkNotification).filter(GroupHomeworkNotification.homework_id == homework.id).delete()
        db.delete(homework)
        db.commit()

def submit_homework_record(
    db: Session, group_id: int, lesson_id: int, user_id: int,
    clean_text: str | None,
    file_url: str | None, file_type: str | None, filename: str | None,
    url: str | None, url_type: str | None, url_filename: str | None,
):
    homework = db.query(GroupHomework).filter(
        GroupHomework.group_id == group_id,
        GroupHomework.lesson_id == lesson_id,
    ).first()
    
    if not homework:
        return None

    submission = db.query(GroupHomeworkSubmission).filter(
        GroupHomeworkSubmission.homework_id == homework.id,
        GroupHomeworkSubmission.student_id == user_id,
    ).first()
    
    is_new = submission is None
    if not submission:
        submission = GroupHomeworkSubmission(
            homework_id=homework.id,
            student_id=user_id,
        )
        db.add(submission)

    if file_url:
        submission.file_url = file_url
        submission.file_type = file_type
        submission.filename = filename
    elif url:
        submission.file_url = url
        submission.file_type = url_type
        submission.filename = url_filename

    submission.text_answer = clean_text
    submission.submitted_at = datetime.utcnow()
    db.commit()
    return submission

def save_review_record(db: Session, group_id: int, submission_id: int, user_id: int, clean_teacher_comment: str | None):
    submission = db.query(GroupHomeworkSubmission).join(GroupHomework).filter(
        GroupHomeworkSubmission.id == submission_id,
        GroupHomework.group_id == group_id,
    ).first()
    
    if not submission:
        return False, None
        
    previous_comment = (submission.teacher_comment or "").strip()
    submission.teacher_comment = clean_teacher_comment
    if clean_teacher_comment and clean_teacher_comment != previous_comment:
        submission.homework_reply_read_at = None
    elif not clean_teacher_comment:
        submission.homework_reply_read_at = None
    submission.reviewed_at = datetime.utcnow()
    submission.reviewed_by_id = user_id
    db.commit()

    try:
        from app.utils.push import send_push_to_user
        send_push_to_user(
            db=db,
            user_id=submission.student_id,
            title="Домашнее задание проверено",
            body="Преподаватель оставил ответ/оценку",
            target_url=f"/dashboard/student/homework-replies/{submission.id}/open",
            notification_type="homework_reviewed",
            entity_id=submission.id
        )
    except Exception as e:
        logger.error(f"Error sending push for homework review: {e}")
        
    return True, submission.homework.lesson_id
