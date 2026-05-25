/**
 * courses.js — Управление курсами на дашборде преподавателя
 * Функции: открытие/закрытие модальных окон, удаление курса
 */

const COURSE_IMAGE_MAX_BYTES = 5 * 1024 * 1024;
const COURSE_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp'];



function getCourseCoverLetter(title) {
  return (title || '?').trim().charAt(0).toUpperCase() || '?';
}

function renderCourseCoverMarkup(course) {
  const title = course?.title || '';
  const safeTitle = escapeHtml(title);
  if (course?.image) {
    return `
      <div class="course-cover">
        <img src="${course.image}" alt="Обложка курса ${safeTitle}" class="course-cover-image" loading="lazy" />
      </div>
    `;
  }

  return `
    <div class="course-cover">
      <div class="course-cover-placeholder">
        <span class="course-cover-letter">${getCourseCoverLetter(title)}</span>
      </div>
    </div>
  `;
}

window.renderCourseCoverMarkup = renderCourseCoverMarkup;

function getUploaderState(root) {
  if (!root._courseCoverState) {
    root._courseCoverState = {
      currentImage: root.dataset.currentImage || '',
      initialImage: root.dataset.currentImage || '',
      previewObjectUrl: '',
    };
  }
  return root._courseCoverState;
}

function revokeUploaderPreviewUrl(state) {
  if (!state?.previewObjectUrl) return;
  URL.revokeObjectURL(state.previewObjectUrl);
  state.previewObjectUrl = '';
}

function setUploaderError(root, message = '') {
  const errorEl = root.querySelector('[data-course-cover-error]');
  if (!errorEl) return;
  errorEl.textContent = message;
  errorEl.style.display = message ? 'block' : 'none';
}

function updateUploaderPreview(root, imageUrl = '') {
  const state = getUploaderState(root);
  const titleInput = document.getElementById(root.dataset.titleSource || '');
  const title = titleInput?.value || root.dataset.title || '';
  const img = root.querySelector('[data-course-cover-preview-image]');
  const placeholder = root.querySelector('[data-course-cover-placeholder]');
  const letter = root.querySelector('[data-course-cover-letter]');
  const removeBtn = root.querySelector('[data-course-cover-remove-btn]');

  if (letter) letter.textContent = getCourseCoverLetter(title);

  if (img && imageUrl) {
    img.src = imageUrl;
    img.hidden = false;
    placeholder.hidden = true;
    root.classList.add('has-image');
  } else {
    if (img) {
      img.removeAttribute('src');
      img.hidden = true;
    }
    if (placeholder) placeholder.hidden = false;
    root.classList.remove('has-image');
  }

  if (removeBtn) {
    removeBtn.hidden = !imageUrl;
  }

  state.currentImage = imageUrl || '';
}

function setCourseCoverUploaderState(rootOrId, options = {}) {
  const root = typeof rootOrId === 'string' ? document.getElementById(rootOrId) : rootOrId;
  if (!root) return;

  const state = getUploaderState(root);
  const input = root.querySelector('[data-course-cover-input]');
  const removeInput = root.querySelector('[data-course-cover-remove]');

  revokeUploaderPreviewUrl(state);
  state.initialImage = options.currentImage ?? state.initialImage ?? '';
  state.currentImage = options.currentImage ?? state.initialImage ?? '';
  root.dataset.currentImage = state.currentImage;
  root.dataset.title = options.title || '';

  if (removeInput) removeInput.value = '0';
  if (input) input.value = '';
  setUploaderError(root, '');
  updateUploaderPreview(root, state.currentImage);
}

window.setCourseCoverUploaderState = setCourseCoverUploaderState;

function resetCourseCoverUploader(rootOrId) {
  setCourseCoverUploaderState(rootOrId, { currentImage: '', title: '' });
}

window.resetCourseCoverUploader = resetCourseCoverUploader;

function validateCourseCoverFile(file) {
  if (!file) return null;

  const ext = (file.name.split('.').pop() || '').toLowerCase();
  if (!COURSE_IMAGE_EXTENSIONS.includes(ext)) {
    return t('validation.image_invalid');
  }
  if (file.size > COURSE_IMAGE_MAX_BYTES) {
    return t('validation.image_too_large');
  }
  return null;
}

function bindCourseCoverUploader(root) {
  if (root.dataset.coverUploaderBound === '1') return;
  root.dataset.coverUploaderBound = '1';

  const input = root.querySelector('[data-course-cover-input]');
  const dropzone = root.querySelector('[data-course-cover-dropzone]');
  const removeInput = root.querySelector('[data-course-cover-remove]');
  const removeBtn = root.querySelector('[data-course-cover-remove-btn]');
  const titleInput = document.getElementById(root.dataset.titleSource || '');
  const state = getUploaderState(root);

  if (!input || !dropzone) return;

  const applyFile = (file) => {
    const error = validateCourseCoverFile(file);
    if (error) {
      input.value = '';
      setUploaderError(root, error);
      updateUploaderPreview(root, state.currentImage);
      return;
    }

    if (removeInput) removeInput.value = '0';
    setUploaderError(root, '');
    revokeUploaderPreviewUrl(state);
    const previewUrl = URL.createObjectURL(file);
    state.previewObjectUrl = previewUrl;
    updateUploaderPreview(root, previewUrl);
  };

  input.addEventListener('change', () => {
    const file = input.files?.[0];
    if (!file) {
      updateUploaderPreview(root, state.currentImage);
      return;
    }
    applyFile(file);
  });

  ['dragenter', 'dragover'].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      root.classList.add('is-dragover');
    });
  });

  ['dragleave', 'dragend', 'drop'].forEach((eventName) => {
    dropzone.addEventListener(eventName, () => {
      root.classList.remove('is-dragover');
    });
  });

  dropzone.addEventListener('drop', (event) => {
    event.preventDefault();
    const file = event.dataTransfer?.files?.[0];
    if (!file) return;

    const dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
    applyFile(file);
  });

  removeBtn?.addEventListener('click', () => {
    revokeUploaderPreviewUrl(state);
    state.currentImage = '';
    if (input) input.value = '';
    if (removeInput) removeInput.value = '1';
    setUploaderError(root, '');
    updateUploaderPreview(root, '');
  });

  titleInput?.addEventListener('input', () => updateUploaderPreview(root, state.currentImage));
  updateUploaderPreview(root, state.currentImage);
}

/**
 * Открывает модальное окно создания курса.
 */
function openCreateModal() {
  const modal = document.getElementById('create-modal');
  if (!modal) return;
  document.getElementById('create-course-form').reset();
  if (typeof setRichTextValue === 'function') {
    setRichTextValue('new-description-input', '');
  }
  resetCourseCoverUploader('create-course-cover-uploader');
  _openModalOverlay('create-modal');
  // Фокус на первое поле
  setTimeout(() => document.getElementById('new-title')?.focus(), 100);
}

/**
 * Открывает модальное окно редактирования курса и заполняет поля.
 * @param {DOMStringMap} dataset
 */
function openEditModal(dataset) {
  const modal = document.getElementById('edit-modal');
  if (!modal) return;

  const form = document.getElementById('edit-course-form');
  form.action = `/courses/${dataset.courseId}/edit`;
  document.getElementById('edit-title').value = dataset.courseTitle || '';
  if (typeof setRichTextValue === 'function') {
    setRichTextValue('edit-description-input', dataset.courseDescription || '');
  }
  const catEl = document.getElementById('edit-category');
  if (catEl) catEl.value = dataset.courseCategory || "0";
  const levelEl = document.getElementById('edit-level');
  if (levelEl) levelEl.value = dataset.courseLevel || "Beginner";
  setCourseCoverUploaderState('edit-course-cover-uploader', {
    currentImage: dataset.courseImage || '',
    title: dataset.courseTitle || ''
  });

  _openModalOverlay('edit-modal');
  setTimeout(() => document.getElementById('edit-title')?.focus(), 100);
}

/**
 * Закрывает модальное окно по id.
 * @param {string} modalId
 */
function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove('open');
  // Unlock body scroll if no modals are visible
  if (!document.querySelector('.modal-overlay.open')) {
    document.body.classList.remove('modal-open');
  }
}

function _openModalOverlay(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    document.body.classList.add('modal-open');
    modal.classList.add('open');
    // Устанавливаем обработчики для предотвращения закрытия при взаимодействии с полями ввода
    _setupModalInputHandlers(modalId);
  }
}

/**
 * Устанавливает обработчики событий для полей ввода внутри модального окна
 * для предотвращения закрытия модального окна при выделении/копировании текста
 * @param {string} modalId
 */
function _setupModalInputHandlers(modalId) {
  const modal = document.getElementById(modalId);
  if (!modal) return;

  // Находим все поля ввода, текстовые области и contenteditable элементы
  const inputElements = modal.querySelectorAll('input, textarea, [contenteditable="true"]');
  
  inputElements.forEach((element) => {
    // Если уже установлены обработчики, пропускаем
    if (element.dataset.modalHandlersSet === '1') return;
    element.dataset.modalHandlersSet = '1';

    // Предотвращаем закрытие модального окна при mouseup/mousedown на input полях
    ['mouseup', 'mousedown', 'click', 'dblclick'].forEach((eventName) => {
      element.addEventListener(eventName, (e) => {
        e.stopPropagation();
      }, true); // Используем capture phase для большей надежности
    });

    // Предотвращаем закрытие при выделении текста
    element.addEventListener('select', (e) => {
      e.stopPropagation();
    });

    // Предотвращаем закрытие при copy/cut/paste
    ['copy', 'cut', 'paste'].forEach((eventName) => {
      element.addEventListener(eventName, (e) => {
        e.stopPropagation();
      });
    });
  });

  // Дополнительно: предотвращаем закрытие при клике на сам modal контейнер (не overlay)
  const modalContent = modal.querySelector('.modal');
  if (modalContent) {
    modalContent.addEventListener('click', (e) => {
      e.stopPropagation();
    });
  }
}

/**
 * Удаляет курс после подтверждения пользователем.
 * @param {number} courseId
 */
async function deleteCourse(courseId) {
  if (!(await showConfirmModal(t('manage.confirm_delete_course')))) return;

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
      openEditModal(btn.dataset);
    });
  });

  document.querySelectorAll('[data-course-cover-uploader]').forEach(bindCourseCoverUploader);

  const createForm = document.getElementById('create-course-form');
  if (createForm) {
    createForm.addEventListener('submit', function (e) {
      const titleInput = document.getElementById('new-title');
      if (!titleInput.value.trim()) {
        e.preventDefault();
        titleInput.classList.add('error');
        titleInput.focus();
        showToast(t('validation.title_required'), 'error');
        return;
      }

      const imageInput = createForm.querySelector('[data-course-cover-input]');
      const file = imageInput?.files?.[0];
      const imageError = validateCourseCoverFile(file);
      if (imageError) {
        e.preventDefault();
        setUploaderError(document.getElementById('create-course-cover-uploader'), imageError);
        showToast(imageError, 'error');
        return;
      }

      // Защита от двойной отправки
      const submitBtn = createForm.querySelector('[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;
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
        return;
      }

      const uploader = editForm.querySelector('[data-course-cover-uploader]');
      const imageInput = editForm.querySelector('[data-course-cover-input]');
      const file = imageInput?.files?.[0];
      const imageError = validateCourseCoverFile(file);
      if (imageError) {
        e.preventDefault();
        setUploaderError(uploader, imageError);
        showToast(imageError, 'error');
        return;
      }

      // Защита от двойной отправки
      const submitBtn = editForm.querySelector('[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;
    });
  }

  // ── Инициализация обработчиков для всех модальных окон ──
  // Устанавливаем обработчики для предотвращения закрытия модалов при работе с полями ввода
  const modalIds = [
    'create-modal', 'edit-modal', 
    'add-module-modal', 'edit-module-modal',
    'add-lesson-modal', 'edit-lesson-modal',
    'edit-course-modal'
  ];
  
  modalIds.forEach(modalId => {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    
    // Инициализируем обработчики для полей ввода
    _setupModalInputHandlers(modalId);
    
    // Также обработчик для overlay - закрытие при клике именно на overlay, не на modal
    const overlay = modal;
    overlay.addEventListener('click', (e) => {
      // Закрываем только если кликнули на сам overlay, а не на modal содержимое
      if (e.target === overlay) {
        closeModal(modalId);
      }
    }, { once: false });
  });
});

window.addEventListener('pagehide', () => {
  document.querySelectorAll('[data-course-cover-uploader]').forEach((root) => {
    revokeUploaderPreviewUrl(getUploaderState(root));
  });
}, { once: true });
