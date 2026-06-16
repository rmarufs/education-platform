const groupManageScript = document.currentScript;
const groupManageConfig = {
    groupId: groupManageScript?.dataset.groupId || '',
    groupBaseUrl: groupManageScript?.dataset.groupId ? `/groups/${groupManageScript.dataset.groupId}` : '',
    nextLessonOrder: groupManageScript?.dataset.nextLessonOrder || '1',
};

window.GOOGLE_FORMS_QUIZ_URL_ENDPOINT = '/groups/api/quiz-url';

function openModal(id) {
    if (typeof _openModalOverlay === 'function') _openModalOverlay(id);
    else { const m = document.getElementById(id); if (m) { m.classList.add('open'); document.body.classList.add('modal-open'); } }
}
function _openModalOverlay(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        document.body.classList.add('modal-open');
        modal.classList.add('open');
    }
}
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.remove('open');
    if (!document.querySelector('.modal-overlay.open')) {
        document.body.classList.remove('modal-open');
    }
}
function filterStudents(q) {
    const sel = document.getElementById('student-select');
    q = q.toLowerCase();
    Array.from(sel.options).forEach(opt => {
        opt.hidden = q && !opt.dataset.name.includes(q);
    });
}

document.getElementById('add-students-form').addEventListener('submit', async function(e) {
    e.preventDefault();

    const select = document.getElementById('student-select');
    const gradeInput = this.querySelector('input[name="grade"]');
    const submitBtn = this.querySelector('button[type="submit"]');
    const selectedIds = Array.from(select.selectedOptions).map(opt => Number(opt.value));

    if (!selectedIds.length) {
        showToast(t('group.select_at_least_one_student'), 'error');
        return;
    }

    submitBtn.disabled = true;
    const originalText = submitBtn.textContent;
    submitBtn.textContent = t('group.adding_students');

    try {
        const res = await fetch(`${groupManageConfig.groupBaseUrl}/students/bulk-add`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                student_ids: selectedIds,
                grade: gradeInput.value ? Number(gradeInput.value) : null,
            }),
        });

        const data = await res.json();
        if (!res.ok || !data.success) {
            throw new Error(data.detail || t('group.add_students_error'));
        }

        select.selectedIndex = -1;
        document.getElementById('student-search').value = '';
        filterStudents('');
        closeModal('add-student-modal');

        window.location.href = `${groupManageConfig.groupBaseUrl}/manage?success=student_bulk_added&added=${data.added_count}&skipped=${data.skipped_count}`;
    } catch (err) {
        showToast(err.message || t('group.add_students_failed'), 'error');
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
    }
});

function openAddLessonModal(moduleId = '') {
    document.getElementById('l-title').value = '';
    document.getElementById('l-video').value = '';
    document.getElementById('l-cover').value = '';
    document.getElementById('l-order').value = groupManageConfig.nextLessonOrder;
    document.getElementById('l-module').value = moduleId || '';
    document.getElementById('l-files').value = '';
    setRichTextValue('l-desc-input', '');
    resetLessonMediaEditor(document.querySelector('#add-lesson-modal [data-lesson-media-editor]'));
    _openModalOverlay('add-lesson-modal');
}
function openEditModuleModal(dataset) {
    const form = document.getElementById('edit-module-form');
    form.action = `${groupManageConfig.groupBaseUrl}/modules/${dataset.moduleId}/edit`;
    document.getElementById('egm-title').value = dataset.moduleTitle || '';
    document.getElementById('egm-order').value = dataset.moduleOrder || '0';
    _openModalOverlay('edit-module-modal');
}
function openEditLessonModal(dataset) {
    const form = document.getElementById('edit-lesson-form');
    form.action = `${groupManageConfig.groupBaseUrl}/lessons/${dataset.lessonId}/edit`;
    document.getElementById('el-title').value = dataset.lessonTitle || '';
    document.getElementById('el-video').value = dataset.lessonVideo || '';
    document.getElementById('el-cover').value = '';
    document.getElementById('el-order').value = dataset.lessonOrder || '0';
    document.getElementById('el-module').value = dataset.lessonModuleId || '';
    document.getElementById('el-files').value = '';
    setRichTextValue('el-desc-input', dataset.lessonDesc || '');
    resetLessonMediaEditor(document.querySelector('#edit-lesson-modal [data-lesson-media-editor]'), dataset.lessonCover || '');
    _openModalOverlay('edit-lesson-modal');
}
function openHomeworkModal(dataset) {
    const lessonId = dataset.lessonId;
    const hasHomework = dataset.hasHomework === '1';
    const form = document.getElementById('homework-form');
    const deleteForm = document.getElementById('homework-delete-form');
    const deleteBtn = document.getElementById('homework-delete-btn');
    const title = document.getElementById('homework-modal-title');
    const currentMaterial = document.getElementById('hw-current-material');
    const deadlineEnabled = document.getElementById('hw-deadline-enabled');
    const deadlineInput = document.getElementById('hw-deadline');
    const deadlineError = document.getElementById('hw-deadline-error');

    form.action = `${groupManageConfig.groupBaseUrl}/lessons/${lessonId}/homework/save`;
    if (hasHomework) {
        deleteForm.action = `${groupManageConfig.groupBaseUrl}/lessons/${lessonId}/homework/delete`;
    } else {
        deleteForm.removeAttribute('action');
    }
    document.getElementById('hw-title').value = dataset.homeworkTitle || '';
    document.getElementById('hw-description').value = dataset.homeworkDescription || '';
    const materialUrl = dataset.homeworkMaterialUrl || '';
    document.getElementById('hw-material-url').value = /^https?:\/\//i.test(materialUrl) ? materialUrl : '';
    document.getElementById('hw-material-file').value = '';
    deadlineInput.value = dataset.homeworkDeadline || '';
    deadlineEnabled.checked = Boolean(dataset.homeworkDeadline);
    updateHomeworkDeadlineField();
    if (deadlineError) deadlineError.textContent = '';
    deleteBtn.hidden = !hasHomework;
    deleteBtn.disabled = !hasHomework;
    deleteBtn.setAttribute('aria-label', typeof t === 'function' ? t('homework.delete_aria') : 'homework.delete_aria');
    title.dataset.i18n = hasHomework ? 'homework.edit' : 'homework.add';
    title.textContent = typeof t === 'function'
        ? t(
            hasHomework ? 'homework.edit' : 'homework.add',
            {},
            hasHomework ? 'Редактировать домашнее задание' : 'Добавить домашнее задание'
        )
        : (hasHomework ? 'Редактировать домашнее задание' : 'Добавить домашнее задание');

    if (dataset.homeworkMaterialUrl) {
        currentMaterial.hidden = false;
        currentMaterial.textContent = `${typeof t === 'function' ? t('homework.current_material', {}, 'Текущий материал') : 'Текущий материал'}: ${dataset.homeworkMaterialFilename || dataset.homeworkMaterialUrl}`;
    } else {
        currentMaterial.hidden = true;
        currentMaterial.textContent = '';
    }

    const confirmBlock = document.getElementById('hw-delete-confirm-block');
    const defaultButtons = document.getElementById('hw-default-buttons');
    if (confirmBlock && defaultButtons) {
        confirmBlock.style.display = 'none';
        defaultButtons.style.display = 'flex';
    }

    _openModalOverlay('homework-modal');
}
function updateHomeworkDeadlineField() {
    const deadlineEnabled = document.getElementById('hw-deadline-enabled');
    const deadlineField = document.getElementById('hw-deadline-field');
    const deadlineInput = document.getElementById('hw-deadline');
    const enabled = Boolean(deadlineEnabled?.checked);
    if (deadlineField) deadlineField.hidden = !enabled;
    if (deadlineInput) {
        deadlineInput.disabled = !enabled;
        deadlineInput.required = enabled;
        if (!enabled) deadlineInput.value = '';
    }
}
document.getElementById('hw-deadline-enabled')?.addEventListener('change', updateHomeworkDeadlineField);
document.getElementById('homework-form')?.addEventListener('submit', (event) => {
    const enabled = document.getElementById('hw-deadline-enabled')?.checked;
    const input = document.getElementById('hw-deadline');
    const error = document.getElementById('hw-deadline-error');
    if (error) error.textContent = '';
    if (enabled && input && !input.value) {
        event.preventDefault();
        if (error) error.textContent = typeof t === 'function' ? t('homework.deadline_required') : 'homework.deadline_required';
        input.focus();
    }
});
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') ['add-module-modal','edit-module-modal','edit-group-modal','add-student-modal','add-lesson-modal','edit-lesson-modal','homework-modal'].forEach(closeModal);
});
