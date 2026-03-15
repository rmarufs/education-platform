/**
 * auth.js — Клиентская валидация форм входа и регистрации
 */

document.addEventListener('DOMContentLoaded', () => {

  // ── Форма ВХОДА ─────────────────────────────────────────────
  const loginForm = document.getElementById('login-form');
  if (loginForm) {
    loginForm.addEventListener('submit', function (e) {
      clearFormErrors(this);
      let valid = true;

      const email = document.getElementById('email');
      const password = document.getElementById('password');

      if (!email.value.trim()) {
        showFieldError('email', t('validation.email_required'));
        valid = false;
      } else if (!isValidEmail(email.value)) {
        showFieldError('email', t('validation.email_invalid'));
        valid = false;
      }

      if (!password.value) {
        showFieldError('password', t('validation.password_required'));
        valid = false;
      }

      if (!valid) e.preventDefault();
    });
  }

  // ── Форма РЕГИСТРАЦИИ ────────────────────────────────────────
  const registerForm = document.getElementById('register-form');
  if (registerForm) {
    registerForm.addEventListener('submit', function (e) {
      clearFormErrors(this);
      let valid = true;

      const name     = document.getElementById('name');
      const email    = document.getElementById('email');
      const password = document.getElementById('password');

      if (!name.value.trim()) {
        showFieldError('name', t('validation.name_required'));
        valid = false;
      }

      if (!email.value.trim()) {
        showFieldError('email', t('validation.email_required'));
        valid = false;
      } else if (!isValidEmail(email.value)) {
        showFieldError('email', t('validation.email_invalid'));
        valid = false;
      }

      if (!password.value) {
        showFieldError('password', t('validation.password_required'));
        valid = false;
      } else if (password.value.length < 6) {
        showFieldError('password', t('validation.password_short'));
        valid = false;
      }

      if (!valid) e.preventDefault();
    });

    // Подсвечиваем выбранную роль
    registerForm.querySelectorAll('input[name="role"]').forEach(radio => {
      radio.addEventListener('change', () => {
        registerForm.querySelectorAll('.role-option').forEach(label => {
          label.style.borderColor = '';
          label.style.background = '';
          label.style.color = '';
        });
      });
    });
  }

});

/**
 * Проверяет формат email.
 * @param {string} email
 * @returns {boolean}
 */
function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}
