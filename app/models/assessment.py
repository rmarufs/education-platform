from datetime import datetime
from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database import Base

class AssessmentResponse(Base):
    __tablename__ = "assessment_responses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    q1_answer = Column(Integer, nullable=False)
    q2_answer = Column(Integer, nullable=False)
    q3_answer = Column(Integer, nullable=False)
    q4_answer = Column(Integer, nullable=False)
    q5_answer = Column(Integer, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связь с пользователем
    user = relationship("User", backref="assessment_response")
