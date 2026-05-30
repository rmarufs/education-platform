function togglePassword(fieldId) {
  const input = document.getElementById(fieldId);
  if (!input) return;
  input.type = input.type === 'password' ? 'text' : 'password';
}

function showToast(message, type = 'success') {
  const existing = document.getElementById('toast');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.id = 'toast';
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);

  requestAnimationFrame(() => toast.classList.add('visible'));

  setTimeout(() => {
    toast.classList.remove('visible');
    setTimeout(() => toast.remove(), 220);
  }, 3500);
}

/* ── Глобальная кастомная confirm-модалка (заменяет нативный confirm) ── */
let _confirmResolve = null;

function resolveModalCopy(value, params = {}) {
  if (typeof value !== 'string' || !value) return '';
  if (window.t) {
    const translated = t(value, params);
    if (translated !== value || value.includes('.')) return translated;
  }
  return value;
}

function showConfirmModal(message, hint = '', confirmText, cancelText, isDanger = true) {
  return new Promise((resolve) => {
    _confirmResolve = resolve;
    const modal = document.getElementById('confirm-modal');
    if (!modal) { resolve(false); return; }
    const normalizedMessage = String(message || '');
    const normalizedHint = String(hint || '');
    const messageParts = !normalizedHint ? normalizedMessage.split(/\n+/) : [normalizedMessage];
    const modalTitle = messageParts.shift().trim();
    const modalHint = normalizedHint || messageParts.join(' ').trim();
    const resolvedConfirmText = confirmText || (window.t ? t('confirm.confirm') : 'Подтвердить');
    const resolvedCancelText = cancelText || (window.t ? t('action.cancel') : 'Отмена');
    const titleEl = document.getElementById('confirm-modal-title');
    if (titleEl) titleEl.textContent = modalTitle;
    const hintEl = document.getElementById('confirm-modal-hint');
    if (hintEl) {
      hintEl.textContent = modalHint;
      hintEl.hidden = !modalHint;
    }
    const confirmBtn = document.getElementById('confirm-modal-ok');
    if (confirmBtn) {
      confirmBtn.textContent = resolvedConfirmText;
      confirmBtn.className = 'btn ' + (isDanger ? 'btn-danger' : 'btn-primary');
    }
    const cancelBtn = document.getElementById('confirm-modal-cancel');
    if (cancelBtn) cancelBtn.textContent = resolvedCancelText;
    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');
    if (confirmBtn) confirmBtn.focus();
  });
}

function _resolveConfirmModal(result) {
  const modal = document.getElementById('confirm-modal');
  if (modal) {
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
    if (!document.querySelector('.modal-overlay.open')) {
      document.body.classList.remove('modal-open');
    }
  }
  if (_confirmResolve) {
    _confirmResolve(result);
    _confirmResolve = null;
  }
}

/**
 * Используется в onsubmit форм вместо нативного browser-confirm.
 * onsubmit="confirmAndSubmit(event, 'Сообщение');"
 */
async function confirmAndSubmit(
  event,
  message,
  hint = '',
  params = null,
  confirmText,
  cancelText,
  isDanger = true,
) {
  event.preventDefault();
  const form = event.target || event.currentTarget;
  const resolvedParams = params && typeof params === 'object' && !Array.isArray(params) ? params : {};
  const confirmed = await showConfirmModal(
    resolveModalCopy(message, resolvedParams),
    resolveModalCopy(hint, resolvedParams),
    resolveModalCopy(confirmText, resolvedParams),
    resolveModalCopy(cancelText, resolvedParams),
    isDanger,
  );
  if (confirmed) {
    form.onsubmit = null;
    form.submit();
  }
}

function showFieldError(fieldId, message) {
  const field = document.getElementById(fieldId);
  if (field) field.classList.add('error');
  const errorEl = document.getElementById(`${fieldId}-error`);
  if (errorEl) errorEl.textContent = message;
}

function clearFormErrors(form) {
  form.querySelectorAll('.form-input').forEach((el) => el.classList.remove('error'));
  form.querySelectorAll('.form-error').forEach((el) => {
    el.textContent = '';
  });
}

document.addEventListener('DOMContentLoaded', () => {
  if (!('IntersectionObserver' in window)) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = '1';
        entry.target.style.transform = 'translateY(0)';
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  document.querySelectorAll('.course-card, .feature-card, .stat-item, .reveal-card, .reveal').forEach((el) => {
    observer.observe(el);
  });

  window.addEventListener('pagehide', () => observer.disconnect(), { once: true });
});

/* ────────────────────────────────────────────────────────────
   Google Forms Integration
──────────────────────────────────────────────────────────────── */

// Open Google Forms in iframe
function openGoogleFormsIframe(formUrl, title) {
  if (!formUrl) {
    showToast(t('manage.google_forms_missing'), 'error');
    return;
  }

  const container = document.getElementById('google-forms-iframe-container');
  if (!container) {
    // Create container if it doesn't exist
    const newContainer = document.createElement('div');
    newContainer.id = 'google-forms-iframe-container';
    newContainer.className = 'active';
    newContainer.innerHTML = `
      <div class="google-forms-iframe-header">
        <h3>${escapeHtml(title)}</h3>
        <button class="google-forms-iframe-close" onclick="closeGoogleFormsIframe()">✕</button>
      </div>
      <div class="google-forms-iframe-body">
        <iframe src="${escapeHtml(formUrl)}&embedded=true" frameborder="0" marginheight="0" marginwidth="0" loading="lazy"></iframe>
      </div>
    `;
    document.body.appendChild(newContainer);
    newContainer.addEventListener('click', (e) => {
      if (e.target === newContainer) closeGoogleFormsIframe();
    });
  } else {
    container.classList.add('active');
    const iframe = container.querySelector('iframe');
    if (iframe) {
      iframe.src = formUrl + '&embedded=true';
    }
    const header = container.querySelector('h3');
    if (header) header.textContent = title;
  }
}

// Close Google Forms iframe
function closeGoogleFormsIframe() {
  const container = document.getElementById('google-forms-iframe-container');
  if (container) {
    container.classList.remove('active');
  }
}

// Open modal to add/edit Google Forms URL
function openGoogleFormsModal(scopeName, scopeId, label, currentUrl = '') {
  const modal = document.getElementById('google-forms-modal');
  const existing = modal || createGoogleFormsModal();

  const title = existing.querySelector('h2');
  if (title) {
    title.textContent = window.t ? t('manage.google_forms_add_title') : 'Добавить ссылку на Google Forms';
  }
  const input = existing.querySelector('input[name="quiz_url"]');
  if (!input) return;
  input.value = currentUrl || '';
  input.placeholder = window.t ? t('manage.google_forms_ph') : 'Вставьте ссылку на Google Forms...';
  
  const form = existing.querySelector('form');
  if (!form) return;
  form.dataset.scopeName = scopeName;
  form.dataset.scopeId = scopeId;
  
  // Переустанавливаем обработчики для полей ввода после обновления
  const inputs = form.querySelectorAll('input, textarea');
  inputs.forEach((inp) => {
    if (inp.dataset.handlersSet !== '1') {
      inp.dataset.handlersSet = '1';
      ['mouseup', 'mousedown', 'click', 'dblclick'].forEach((eventName) => {
        inp.addEventListener(eventName, (e) => {
          e.stopPropagation();
        }, true);
      });
      inp.addEventListener('select', (e) => {
        e.stopPropagation();
      });
      ['copy', 'cut', 'paste'].forEach((eventName) => {
        inp.addEventListener(eventName, (e) => {
          e.stopPropagation();
        });
      });
    }
  });
  
  existing.classList.add('active');
  input.focus();
}

function getGoogleFormsButtonPayload(button) {
  return {
    scopeName: button.dataset.googleFormsScopeName || '',
    scopeId: button.dataset.googleFormsScopeId || '',
    label: button.dataset.googleFormsLabel || '',
    currentUrl: button.dataset.googleFormsCurrentUrl || '',
  };
}

function initGoogleFormsAuthoring(scope = document) {
  if (!scope || scope.dataset?.googleFormsAuthoringReady === '1') return;
  if (scope.dataset) scope.dataset.googleFormsAuthoringReady = '1';

  scope.addEventListener('click', (event) => {
    const button = event.target.closest('[data-google-forms-action]');
    if (!button) return;

    const payload = getGoogleFormsButtonPayload(button);
    if (!payload.scopeName || !payload.scopeId) return;

    event.preventDefault();
    if (button.dataset.googleFormsAction === 'delete') {
      deleteGoogleFormsUrl(payload.scopeName, payload.scopeId);
      return;
    }
    openGoogleFormsModal(payload.scopeName, payload.scopeId, payload.label, payload.currentUrl);
  });
}

// Create Google Forms modal if it doesn't exist
function createGoogleFormsModal() {
  const existing = document.getElementById('google-forms-modal');
  if (existing) return existing;
  const title = window.t ? t('manage.google_forms_add_title') : 'Добавить ссылку на Google Forms';
  const urlLabel = window.t ? t('manage.google_forms_url') : 'Ссылка на Google Forms';
  const urlPlaceholder = window.t ? t('manage.google_forms_ph') : 'Вставьте ссылку на Google Forms...';
  const closeText = window.t ? t('action.close') : 'Закрыть';
  const cancelText = window.t ? t('action.cancel') : 'Отмена';
  const saveText = window.t ? t('action.save') : 'Сохранить';
  
  const modal = document.createElement('div');
  modal.id = 'google-forms-modal';
  modal.innerHTML = `
    <div class="google-forms-modal-content">
      <div class="google-forms-modal-header">
        <h2>${escapeHtml(title)}</h2>
        <button type="button" onclick="closeGoogleFormsModal()" aria-label="${escapeHtml(closeText)}" style="background:none;border:none;font-size:1.5rem;cursor:pointer;color:var(--text-muted);">✕</button>
      </div>
      <div class="google-forms-modal-body">
        <form class="google-forms-modal-form" id="google-forms-form">
          <div>
            <label for="quiz-url-input">${escapeHtml(urlLabel)}</label>
            <input type="url" id="quiz-url-input" name="quiz_url" placeholder="${escapeHtml(urlPlaceholder)}" required />
          </div>
          <div style="display:flex;gap:12px;justify-content:flex-end;">
            <button type="button" class="btn btn-outline" onclick="closeGoogleFormsModal()">${cancelText}</button>
            <button type="submit" class="btn btn-primary">${saveText}</button>
          </div>
        </form>
      </div>
    </div>
  `;
  
  // Обработчик закрытия при клике на backdrop
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeGoogleFormsModal();
  });

  // Предотвращаем закрытие при клике на само содержимое модального окна
  const content = modal.querySelector('.google-forms-modal-content');
  if (content) {
    content.addEventListener('click', (e) => {
      e.stopPropagation();
    });
  }

  // Устанавливаем обработчики для полей ввода
  const form = modal.querySelector('#google-forms-form');
  if (form) {
    const inputs = form.querySelectorAll('input, textarea');
    inputs.forEach((input) => {
      ['mouseup', 'mousedown', 'click', 'dblclick'].forEach((eventName) => {
        input.addEventListener(eventName, (e) => {
          e.stopPropagation();
        }, true);
      });
      input.addEventListener('select', (e) => {
        e.stopPropagation();
      });
      ['copy', 'cut', 'paste'].forEach((eventName) => {
        input.addEventListener(eventName, (e) => {
          e.stopPropagation();
        });
      });
    });
    form.addEventListener('submit', handleGoogleFormsSubmit);
  }
  
  document.body.appendChild(modal);
  return modal;
}

// Handle Google Forms form submission
async function handleGoogleFormsSubmit(e) {
  e.preventDefault();
  
  const form = e.target;
  const scopeName = form.dataset.scopeName;
  const scopeId = form.dataset.scopeId;
  const quizUrl = form.querySelector('input[name="quiz_url"]').value.trim();
  
  if (!quizUrl) {
    showToast(t('manage.google_forms_required'), 'error');
    return;
  }
  
  // Validate URL format
  try {
    new URL(quizUrl);
  } catch {
    showToast(t('manage.google_forms_invalid'), 'error');
    return;
  }

  // Защита от двойной отправки
  const submitBtn = form.querySelector('[type="submit"]');
  if (submitBtn) submitBtn.disabled = true;
  
  try {
    const formData = new FormData();
    formData.append('scope_name', scopeName);
    formData.append('scope_id', scopeId);
    formData.append('quiz_url', quizUrl);
    
    const endpoint = window.GOOGLE_FORMS_QUIZ_URL_ENDPOINT || '/courses/api/quiz-url';
    const response = await fetch(endpoint, {
      method: 'POST',
      body: formData,
    });
    
    if (!response.ok) {
      const data = await readGoogleFormsResponse(response);
      showToast(data.detail || t('manage.google_forms_save_error'), 'error');
      if (submitBtn) submitBtn.disabled = false;
      return;
    }
    
    showToast(t('manage.google_forms_saved'), 'success');
    closeGoogleFormsModal();
    
    // Refresh the page to show updated content
    window.location.reload();
  } catch (error) {
    console.error('Error:', error);
    showToast(t('manage.google_forms_save_error'), 'error');
    if (submitBtn) submitBtn.disabled = false;
  }
}

// Close Google Forms modal
function closeGoogleFormsModal() {
  const modal = document.getElementById('google-forms-modal');
  if (modal) {
    modal.classList.remove('active');
  }
}

// Delete Google Forms URL
async function deleteGoogleFormsUrl(scopeName, scopeId) {
  const confirmed = await showConfirmModal(
    t('manage.google_forms_delete'),
    t('confirm.action_irreversible'),
    t('action.delete'),
    t('action.cancel'),
    true
  );
  if (!confirmed) return;
  
  try {
    const formData = new FormData();
    formData.append('scope_name', scopeName);
    formData.append('scope_id', scopeId);
    
    const endpoint = window.GOOGLE_FORMS_QUIZ_URL_ENDPOINT || '/courses/api/quiz-url';
    const response = await fetch(endpoint, {
      method: 'DELETE',
      body: formData,
    });
    
    if (!response.ok) {
      const data = await readGoogleFormsResponse(response);
      showToast(data.detail || t('manage.google_forms_delete_error'), 'error');
      return;
    }
    
    showToast(t('manage.google_forms_deleted'), 'success');
    window.location.reload();
  } catch (error) {
    console.error('Error:', error);
    showToast(t('manage.google_forms_delete_error'), 'error');
  }
}

async function readGoogleFormsResponse(response) {
  try {
    return await response.json();
  } catch {
    return { detail: '' };
  }
}

// Helper function to escape HTML
function escapeHtml(text) {
  text = String(text ?? '');
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  };
  return text.replace(/[&<>"']/g, (m) => map[m]);
}

window.openGoogleFormsIframe = openGoogleFormsIframe;
window.closeGoogleFormsIframe = closeGoogleFormsIframe;
window.openGoogleFormsModal = openGoogleFormsModal;
window.closeGoogleFormsModal = closeGoogleFormsModal;
window.deleteGoogleFormsUrl = deleteGoogleFormsUrl;

document.addEventListener('DOMContentLoaded', () => {
  initGoogleFormsAuthoring(document);
});

/* ── Глобальная защита от двойной отправки форм ── */
(function() {
  document.addEventListener('submit', function(e) {
    const form = e.target;

    // Не трогать формы которые имеют свой обработчик в auth.js
    if (form.id === 'login-form' || form.id === 'register-form') return;

    if (form.dataset.submitted === 'true') {
      e.preventDefault();
      return;
    }
    
    form.dataset.submitted = 'true';
    const btn = form.querySelector('button[type="submit"]');
    if (btn) {
      btn.disabled = true;
      btn.style.opacity = '0.6';
      btn.style.pointerEvents = 'none';

      /* Восстановить через 5 сек (на случай ошибки валидации в браузере) */
      setTimeout(function() {
        btn.disabled = false;
        btn.style.opacity = '';
        btn.style.pointerEvents = '';
        form.dataset.submitted = '';
      }, 5000);
    }
  }, true);
})();

/* ── Загрузка аватара из сайдбара ── */
async function uploadSidebarAvatar(input) {
    if (!input.files[0]) return;
    const wrapper = input.closest('.sidebar-profile') || input.parentElement;
    const formData = new FormData();
    formData.append('file', input.files[0]);
    
    if (wrapper) wrapper.style.opacity = '0.5';

    try {
        const res = await fetch('/profile/avatar', {method: 'POST', body: formData});
        const data = await res.json();
        console.log('Avatar response:', data); // для отладки
        if (data.success && data.url) {
            // Ищем img или placeholder внутри wrapper
            let img = wrapper.querySelector('img.avatar');
            const ph = wrapper.querySelector('.avatar-placeholder');
            if (img) {
                img.src = data.url + '?t=' + Date.now();
            } else if (ph) {
                ph.outerHTML = `<img src="${data.url}" class="avatar" id="sidebar-avatar-img" style="border-radius:50%;object-fit:cover;">`;
            }
            if (typeof showToast === 'function') showToast('Фото обновлено', 'success');
        } else {
            console.error('Upload failed:', data);
            if (typeof showToast === 'function') showToast(data.error || 'Ошибка загрузки', 'error');
        }
    } catch(e) {
        console.error('Upload error:', e);
        if (typeof showToast === 'function') showToast('Ошибка соединения', 'error');
    } finally {
        if (wrapper) wrapper.style.opacity = '1';
        input.value = '';
    }
}

/* ── Глобальный индикатор загрузки страниц ───────────────────────────────
   Показывает тонкую shimmer-полоску под navbar при MPA-переходах.
   Не срабатывает для: anchor, mailto/tel/js, download, _blank,
   modifier-click, lang-switcher, theme-btn, logout-modal.
   Скрывается при pageshow (включая bfcache restore в Safari/iOS).
   ───────────────────────────────────────────────────────────────────── */
(function () {
  'use strict';

  var DELAY_MS = 150; // не мигать при быстрых переходах (< 150ms)
  var _timer   = null;
  var _active  = false;

  function getLoader() {
    return document.getElementById('nav-loader');
  }

  function show() {
    if (_active) return;
    _timer = setTimeout(function () {
      var el = getLoader();
      if (!el) return;
      _active = true;
      el.removeAttribute('aria-hidden');
      el.classList.add('nav-loader-active');
    }, DELAY_MS);
  }

  function hide() {
    clearTimeout(_timer);
    _timer  = null;
    _active = false;
    var el = getLoader();
    if (!el) return;
    el.setAttribute('aria-hidden', 'true');
    el.classList.remove('nav-loader-active');
    document.body.classList.remove('nav-loader-debug');
  }

  /* ── Скрыть при загрузке/восстановлении страницы ── */
  // pageshow срабатывает и при обычной загрузке, и при bfcache restore (persisted=true)
  window.addEventListener('pageshow', function () { hide(); });
  // load — дополнительная страховка
  window.addEventListener('load', function () { hide(); });

  /* ── DEBUG: ?debug_loader=1 — показать loader на 2с для визуальной проверки ── */
  // Безопасно: не влияет на обычных пользователей без этого параметра
  window.addEventListener('load', function () {
    try {
      if (new URLSearchParams(window.location.search).get('debug_loader') === '1') {
        var el = getLoader();
        if (!el) return;
        document.body.classList.add('nav-loader-debug');
        el.removeAttribute('aria-hidden');
        el.classList.add('nav-loader-active');
        setTimeout(function () {
          hide();
        }, 2000);
      }
    } catch (_) {}
  });

  /* ── Сбросить таймер при уходе со страницы ── */
  // Не скрываем здесь — скроем при pageshow следующей страницы.
  // Но сбрасываем таймер, чтобы не было ложного показа при быстрой отмене.
  window.addEventListener('pagehide', function () {
    clearTimeout(_timer);
    _timer = null;
  });

  /* ── Перехват кликов по ссылкам ── */
  document.addEventListener('click', function (e) {
    // Только левая кнопка мыши без модификаторов
    if (e.button !== 0)                          return;
    if (e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;

    var link = e.target.closest('a[href]');
    if (!link) return;

    var href = link.getAttribute('href') || '';

    // --- Исключения: не навигационные клики ---

    // Anchor, пустой href, служебные протоколы
    if (href === '' || href === '#')             return;
    if (/^#/.test(href))                         return; // любой anchor
    if (/^(mailto:|tel:|javascript:)/i.test(href)) return;

    // Открытие в новой вкладке
    if (link.target === '_blank')                return;

    // Скачивание файла
    if (link.hasAttribute('download'))           return;

    // Переключатель языка (.lang-switcher → setLang())
    if (link.closest('.lang-switcher'))          return;

    // Кнопка темы — это <button>, не <a>, но страховка
    if (link.id === 'theme-btn')                 return;

    // Logout-ссылка открывает modal, а не переходит на новую страницу
    if (link.hasAttribute('data-logout-link'))   return;

    // Ссылка «Кабинет» в mobile-menu ведёт на /dashboard — навигация, loader нужен
    // Ничего не исключаем здесь — обычная ссылка

    show();
  }, true); // capture: перехватываем до других обработчиков

  /* ── Перехват отправки форм ── */
  document.addEventListener('submit', function (e) {
    // Если форма заблокирована другим обработчиком через e.preventDefault(),
    // defaultPrevented будет true — не показываем loader.
    // Важно: проверка в capture-фазе, до обработчиков формы.
    // Поэтому используем bubbling-фазу (capture: false по умолчанию),
    // чтобы другие обработчики успели заблокировать форму первыми.
    if (e.defaultPrevented) return;

    // Google Forms и confirm-modal уже блокируют submit через preventDefault.
    // register-form и login-form делают нативный submit — loader нужен.
    show();
  }); // bubbling: вызывается после других submit-обработчиков

})();
