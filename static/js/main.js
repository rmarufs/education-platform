/**
 * main.js — Общие утилиты платформы
 */

/**
 * Показывает/скрывает поле пароля.
 * @param {string} fieldId
 */
function togglePassword(fieldId) {
  const input = document.getElementById(fieldId);
  if (!input) return;
  input.type = input.type === 'password' ? 'text' : 'password';
}

/**
 * Показывает уведомление (toast) в верхней части экрана.
 * @param {string} message
 * @param {'success'|'error'} type
 */
function showToast(message, type = 'success') {
  const existing = document.getElementById('toast');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.id = 'toast';
  toast.textContent = message;
  Object.assign(toast.style, {
    position:     'fixed',
    top:          '80px',
    right:        '24px',
    padding:      '12px 20px',
    borderRadius: '8px',
    fontFamily:   'Inter, sans-serif',
    fontSize:     '.875rem',
    fontWeight:   '600',
    zIndex:       '999',
    boxShadow:    '0 4px 12px rgba(0,0,0,.15)',
    animation:    'fadeInUp .3s ease',
    background:   type === 'success' ? '#f0fdf4' : '#fef2f2',
    color:        type === 'success' ? '#16a34a' : '#dc2626',
    border:       `1px solid ${type === 'success' ? '#bbf7d0' : '#fecaca'}`,
  });
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

/**
 * Показывает сообщение об ошибке под полем формы.
 * @param {string} fieldId — id поля
 * @param {string} message — текст ошибки
 */
function showFieldError(fieldId, message) {
  const field = document.getElementById(fieldId);
  if (field) field.classList.add('error');
  const errorEl = document.getElementById(`${fieldId}-error`);
  if (errorEl) errorEl.textContent = message;
}

/**
 * Сбрасывает все ошибки формы.
 * @param {HTMLFormElement} form
 */
function clearFormErrors(form) {
  form.querySelectorAll('.form-input').forEach(el => el.classList.remove('error'));
  form.querySelectorAll('.form-error').forEach(el => el.textContent = '');
}

// Инициализация: плавное появление секций при скролле
document.addEventListener('DOMContentLoaded', () => {
  // IntersectionObserver для анимации карточек
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.style.opacity = '1';
          entry.target.style.transform = 'translateY(0)';
        }
      });
    },
    { threshold: 0.1 }
  );

  document.querySelectorAll('.course-card, .feature-card, .stat-item').forEach(el => {
    observer.observe(el);
  });
});
