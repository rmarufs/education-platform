# Импорт моделей для удобного использования и регистрации в Alembic
from app.models.group import Group, GroupMember, GroupModule, GroupLesson, GroupMaterial, GroupJournalEntry, GroupLessonProgress, GroupHomework, GroupHomeworkSubmission, GroupHomeworkNotification, GroupPaymentEntry
from app.models.organization import OrganizationAnnouncement, OrganizationAnnouncementDismissal
from app.models.vocabulary import VocabularySet, VocabularyItem, VocabularyAttempt, VocabularyAttemptAnswer
