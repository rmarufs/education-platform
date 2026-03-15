/**
 * courses.js — Управление курсами на дашборде преподавателя
 * Функции: открытие/закрытие модальных окон, удаление курса
 */

/**
 * Открывает модальное окно создания курса.
 */
function openCreateModal() {
  const modal = document.getElementById('create-modal');
  if (!modal) return;
  document.getElementById('create-course-form').reset();
  modal.classList.add('open');
  // Фокус на первое поле
  setTimeout(() => document.getElementById('new-title')?.focus(), 100);
}

/**
 * Открывает модальное окно редактирования курса и заполняет поля.
 * @param {number} id
 * @param {string} title
 * @param {string} description
 * @param {string} categoryId
 * @param {string} level
 */
function openEditModal(id, title, description, categoryId, level) {
  const modal = document.getElementById('edit-modal');
  if (!modal) return;

  const form = document.getElementById('edit-course-form');
  form.action = `/courses/${id}/edit`;
  document.getElementById('edit-title').value = title;
  document.getElementById('edit-description').value = description;
  const catEl = document.getElementById('edit-category');
  if (catEl) catEl.value = categoryId || "0";
  const levelEl = document.getElementById('edit-level');
  if (levelEl) levelEl.value = level || "Beginner";

  modal.classList.add('open');
  setTimeout(() => document.getElementById('edit-title')?.focus(), 100);
}

/**
 * Закрывает модальное окно по id.
 * @param {string} modalId
 */
function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove('open');
}

/**
 * Удаляет курс после подтверждения пользователем.
 * @param {number} courseId
 */
async function deleteCourse(courseId) {
  if (!confirm(t('manage.confirm_delete_course'))) return;

  try {
    const response = await fetch(`/courses/${courseId}/delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });

    if (response.ok || response.redirected) {
      // Удаляем карточку из DOM без перезагрузки
      const card = document.getElementById(`course-card-${courseId}`);
      if (card) {
        card.style.transition = 'opacity .3s ease, transform .3s ease';
        card.style.opacity = '0';
        card.style.transform = 'scale(0.95)';
        setTimeout(() => {
          card.remove();
          // Если курсов не осталось — перезагружаем для показа empty state
          const grid = document.querySelector('.courses-grid');
          if (grid && grid.children.length === 0) window.location.reload();
        }, 300);
      }
      showToast(t('action.delete') + ' ✓', 'success');
    } else {
      showToast(t('common.error_delete'), 'error');
    }
  } catch (err) {
    showToast(t('common.error_conn'), 'error');
  }
}

// Закрытие модального окна по Escape
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeModal('create-modal');
    closeModal('edit-modal');
  }
});

// Валидация и привязка кнопок
document.addEventListener('DOMContentLoaded', () => {
  // Привязка удаления
  document.querySelectorAll('.delete-course-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      deleteCourse(btn.dataset.courseId);
    });
  });

  // Привязка редактирования
  document.querySelectorAll('.edit-course-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      openEditModal(
        btn.dataset.courseId,
        btn.dataset.courseTitle,
        btn.dataset.courseDescription,
        btn.dataset.courseCategory,
        btn.dataset.courseLevel
      );
    });
  });

  const createForm = document.getElementById('create-course-form');
  if (createForm) {
    createForm.addEventListener('submit', function (e) {
      const titleInput = document.getElementById('new-title');
      if (!titleInput.value.trim()) {
        e.preventDefault();
        titleInput.classList.add('error');
        titleInput.focus();
        showToast(t('validation.title_required'), 'error');
      }
    });
  }

  const editForm = document.getElementById('edit-course-form');
  if (editForm) {
    editForm.addEventListener('submit', function (e) {
      const titleInput = document.getElementById('edit-title');
      if (!titleInput.value.trim()) {
        e.preventDefault();
        titleInput.classList.add('error');
        titleInput.focus();
        showToast(t('validation.title_required'), 'error');
      }
    });
  }
});
