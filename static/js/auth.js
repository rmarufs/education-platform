/**
 * auth.js — Клиентская валидация форм входа и регистрации
 * Формы отправляются нативным HTML POST (без fetch) для
 * корректной работы сессионных кук и редиректов сервера.
 */

document.addEventListener('DOMContentLoaded', () => {

  // ── Форма ВХОДА ─────────────────────────────────────────────
  const loginForm = document.getElementById('login-form');
  if (loginForm) {
    loginForm.addEventListener('submit', function (e) {
      clearFormErrors(this);
      let valid = true;

      const email    = document.getElementById('email');
      const password = document.getElementById('password');

      if (!email.value.trim()) {
        showFieldError('email', t('validation.email_required') || 'Введите email');
        valid = false;
      } else if (!isValidEmail(email.value)) {
        showFieldError('email', t('validation.email_invalid') || 'Неверный формат email');
        valid = false;
      }

      if (!password.value) {
        showFieldError('password', t('validation.password_required') || 'Введите пароль');
        valid = false;
      }

      // При невалидных данных — не отправляем
      if (!valid) {
        e.preventDefault();
        return;
      }

      // Блокируем кнопку только при валидной отправке
      const btn = this.querySelector('button[type="submit"]');
      if (btn) {
        btn.disabled = true;
        btn.style.opacity = '0.7';
        // Разблокируем через 6 сек на случай ошибки браузера
        setTimeout(() => {
          btn.disabled = false;
          btn.style.opacity = '';
        }, 6000);
      }
      // Форма отправляется нативным POST
    });
  }

  // ── Форма ЗАПРОСА ВОССТАНОВЛЕНИЯ ───────────────────────────
  const forgotPasswordForm = document.getElementById('forgot-password-form');
  if (forgotPasswordForm) {
    forgotPasswordForm.addEventListener('submit', function (e) {
      clearFormErrors(this);
      const email = document.getElementById('email');

      if (!email.value.trim()) {
        showFieldError('email', t('validation.email_required') || 'Введите email');
        e.preventDefault();
        return;
      }

      if (!isValidEmail(email.value)) {
        showFieldError('email', t('validation.email_invalid') || 'Введите корректный email');
        e.preventDefault();
      }
    });
  }

  // ── Форма НОВОГО ПАРОЛЯ ────────────────────────────────────
  const resetPasswordForm = document.getElementById('reset-password-form');
  if (resetPasswordForm) {
    resetPasswordForm.addEventListener('submit', function (e) {
      clearFormErrors(this);
      let valid = true;

      const password = document.getElementById('password');
      const passwordConfirm = document.getElementById('password_confirm');

      if (!password.value) {
        showFieldError('password', t('validation.password_required') || 'Введите пароль');
        valid = false;
      } else if (password.value.length < 6) {
        showFieldError('password', t('validation.password_short') || 'Минимум 6 символов');
        valid = false;
      }

      if (!passwordConfirm.value) {
        showFieldError('password_confirm', t('validation.password_required') || 'Введите пароль');
        valid = false;
      } else if (password.value && password.value !== passwordConfirm.value) {
        showFieldError('password_confirm', t('password_reset.password_mismatch') || 'Пароли не совпадают');
        valid = false;
      }

      if (!valid) e.preventDefault();
    });
  }

  // ── Форма РЕГИСТРАЦИИ ────────────────────────────────────────
  const registerForm = document.getElementById('register-form');
  if (registerForm) {
    registerForm.addEventListener('submit', function (e) {
      if (e.defaultPrevented) return;
      clearFormErrors(this);
      let valid = true;

      const name     = document.getElementById('name');
      const email    = document.getElementById('email');
      const password = document.getElementById('password');

      if (!name.value.trim()) {
        showFieldError('name', t('validation.name_required') || 'Введите имя');
        valid = false;
      }

      if (!email.value.trim()) {
        showFieldError('email', t('validation.email_required') || 'Введите email');
        valid = false;
      } else if (!isValidEmail(email.value)) {
        showFieldError('email', t('validation.email_invalid') || 'Неверный формат email');
        valid = false;
      }

      if (!password.value) {
        showFieldError('password', t('validation.password_required') || 'Введите пароль');
        valid = false;
      } else if (password.value.length < 6) {
        showFieldError('password', t('validation.password_short') || 'Минимум 6 символов');
        valid = false;
      }

      if (!valid) {
        e.preventDefault();
        return;
      }

      const btn = this.querySelector('button[type="submit"]');
      if (btn) {
        btn.disabled = true;
        btn.style.opacity = '0.7';
        setTimeout(() => {
          btn.disabled = false;
          btn.style.opacity = '';
        }, 6000);
      }
      // Форма отправляется нативным POST
    });

    // Подсвечиваем выбранную роль
    registerForm.querySelectorAll('input[name="role"]').forEach(radio => {
      radio.addEventListener('change', () => {
        registerForm.querySelectorAll('.role-option').forEach(label => {
          label.style.borderColor = '';
          label.style.background  = '';
          label.style.color       = '';
        });
      });
    });
  }

});

/**
 * Проверяет формат email.
 */
function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}
