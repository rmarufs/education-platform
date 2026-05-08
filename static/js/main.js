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

  document.querySelectorAll('.course-card, .feature-card, .stat-item, .reveal-card').forEach((el) => {
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
    showToast('Форма не была добавлена', 'error');
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
  
  existing.querySelector('h2').textContent = 'Добавить ссылку на Google Forms';
  const input = existing.querySelector('input[name="quiz_url"]');
  input.value = currentUrl || '';
  input.placeholder = 'Вставьте ссылку на Google Forms...';
  
  const form = existing.querySelector('form');
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

// Create Google Forms modal if it doesn't exist
function createGoogleFormsModal() {
  const existing = document.getElementById('google-forms-modal');
  if (existing) return existing;
  
  const modal = document.createElement('div');
  modal.id = 'google-forms-modal';
  modal.innerHTML = `
    <div class="google-forms-modal-content">
      <div class="google-forms-modal-header">
        <h2>Добавить ссылку на Google Forms</h2>
        <button type="button" onclick="closeGoogleFormsModal()" style="background:none;border:none;font-size:1.5rem;cursor:pointer;color:var(--text-muted);">✕</button>
      </div>
      <div class="google-forms-modal-body">
        <form class="google-forms-modal-form" id="google-forms-form">
          <div>
            <label for="quiz-url-input">Ссылка на Google Forms</label>
            <input type="url" id="quiz-url-input" name="quiz_url" placeholder="https://forms.gle/..." required />
          </div>
          <div style="display:flex;gap:12px;justify-content:flex-end;">
            <button type="button" class="btn btn-outline" onclick="closeGoogleFormsModal()">Отмена</button>
            <button type="submit" class="btn btn-primary">Сохранить</button>
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
    showToast('Пожалуйста, введите ссылку', 'error');
    return;
  }
  
  // Validate URL format
  try {
    new URL(quizUrl);
  } catch {
    showToast('Введите корректную ссылку', 'error');
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
    
    const response = await fetch(`/courses/api/quiz-url`, {
      method: 'POST',
      body: formData,
    });
    
    if (!response.ok) {
      const data = await response.json();
      showToast(data.detail || 'Ошибка при сохранении', 'error');
      if (submitBtn) submitBtn.disabled = false;
      return;
    }
    
    showToast('Ссылка сохранена успешно', 'success');
    closeGoogleFormsModal();
    
    // Refresh the page to show updated content
    window.location.reload();
  } catch (error) {
    console.error('Error:', error);
    showToast('Ошибка при сохранении ссылки', 'error');
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
  if (!confirm('Вы уверены, что хотите удалить ссылку на Google Forms?')) {
    return;
  }
  
  try {
    const formData = new FormData();
    formData.append('scope_name', scopeName);
    formData.append('scope_id', scopeId);
    
    const response = await fetch(`/courses/api/quiz-url`, {
      method: 'DELETE',
      body: formData,
    });
    
    if (!response.ok) {
      const data = await response.json();
      showToast(data.detail || 'Ошибка при удалении', 'error');
      return;
    }
    
    showToast('Ссылка удалена', 'success');
    window.location.reload();
  } catch (error) {
    console.error('Error:', error);
    showToast('Ошибка при удалении ссылки', 'error');
  }
}

// Helper function to escape HTML
function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  };
  return text.replace(/[&<>"']/g, (m) => map[m]);
}

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

