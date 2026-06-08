from datetime import datetime
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship, backref
from app.database import Base


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (
        Index("ix_comments_lesson_parent_created_at", "lesson_id", "parent_comment_id", "created_at"),
        Index("ix_comments_user_id", "user_id"),
    )

    id                = Column(Integer, primary_key=True, index=True)
    lesson_id         = Column(Integer, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    user_id           = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    text              = Column(Text, nullable=False)
    parent_comment_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)
    created_at        = Column(DateTime, default=datetime.utcnow)

    lesson  = relationship("Lesson", back_populates="comments")
    author  = relationship("User")

    # Ответы: используем backref-подход; delete-orphan убран (несовместим с self-ref)
    replies = relationship(
        "Comment",
        backref=backref("parent", remote_side=[id]),
    )
