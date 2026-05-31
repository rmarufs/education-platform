(function () {
  const MIN_DURATION = 500;
  const MAX_DURATION = 2000;
  const MOBILE_QUERY = '(pointer: coarse)';
  const TABLET_QUERY = '(max-width: 1024px)';
  const CLICKABLE_SELECTOR = [
    'a',
    'button',
    '[role="button"]',
    'input[type="submit"]',
    'input[type="button"]',
  ].join(',');

  const coarsePointer = window.matchMedia ? window.matchMedia(MOBILE_QUERY) : null;
  const tabletWidth = window.matchMedia ? window.matchMedia(TABLET_QUERY) : null;

  let progressEl = null;
  let startTime = 0;
  let finishTimer = 0;
  let maxTimer = 0;
  let fetchCount = 0;
  let isRunning = false;

  function isMobileFeedbackEnabled() {
    return Boolean(coarsePointer?.matches && tabletWidth?.matches);
  }

  function ensureProgressEl() {
    if (progressEl || !document.body) return progressEl;
    progressEl = document.getElementById('mobile-click-progress');
    if (!progressEl) {
      progressEl = document.createElement('div');
      progressEl.id = 'mobile-click-progress';
      progressEl.setAttribute('aria-hidden', 'true');
      document.body.appendChild(progressEl);
    }
    return progressEl;
  }

  function clearTimers() {
    if (finishTimer) window.clearTimeout(finishTimer);
    if (maxTimer) window.clearTimeout(maxTimer);
    finishTimer = 0;
    maxTimer = 0;
  }

  function armMaxTimer() {
    if (maxTimer) return;
    maxTimer = window.setTimeout(() => {
      maxTimer = 0;
      if (fetchCount <= 0) finishFeedback();
    }, MAX_DURATION);
  }

  function startFeedback() {
    if (!isMobileFeedbackEnabled()) return;
    const el = ensureProgressEl();
    if (!el) return;

    if (isRunning) {
      if (finishTimer) {
        window.clearTimeout(finishTimer);
        finishTimer = 0;
      }
      el.classList.remove('is-finishing');
      el.classList.add('is-active');
      armMaxTimer();
      return;
    }

    clearTimers();
    startTime = Date.now();
    isRunning = true;

    el.classList.remove('is-finishing');
    el.style.transform = 'scaleX(0)';

    window.requestAnimationFrame(() => {
      el.classList.add('is-active');
      el.style.transform = 'scaleX(0.72)';
    });

    armMaxTimer();
  }

  function finishFeedback() {
    if (!isRunning) return;
    const elapsed = Date.now() - startTime;
    const delay = Math.max(0, MIN_DURATION - elapsed);

    if (finishTimer) window.clearTimeout(finishTimer);
    finishTimer = window.setTimeout(() => {
      const el = progressEl;
      if (!el) return;

      isRunning = false;
      clearTimers();
      el.style.transform = 'scaleX(1)';
      el.classList.add('is-finishing');
      el.classList.remove('is-active');

      window.setTimeout(() => {
        if (isRunning || !progressEl) return;
        progressEl.classList.remove('is-finishing');
        progressEl.style.transform = 'scaleX(0)';
      }, 240);
    }, delay);
  }

  function cancelFeedback() {
    isRunning = false;
    fetchCount = 0;
    clearTimers();
    if (!progressEl) return;
    progressEl.classList.remove('is-active', 'is-finishing');
    progressEl.style.transform = 'scaleX(0)';
  }

  function isDisabled(element) {
    return Boolean(
      element.disabled ||
      element.getAttribute('aria-disabled') === 'true' ||
      element.closest('[aria-disabled="true"]') ||
      element.closest('[disabled]')
    );
  }

  function hasNoLoadingOptOut(element) {
    return Boolean(element.closest('[data-no-loading]'));
  }

  function isFileInput(element) {
    return element.matches('input[type="file"]') || Boolean(element.closest('input[type="file"]'));
  }

  function isSubmitControl(element) {
    if (!element) return false;
    if (element.matches('input[type="submit"]')) return true;
    if (!element.matches('button')) return false;

    const type = (element.getAttribute('type') || '').toLowerCase();
    return (type === '' || type === 'submit') && Boolean(element.form || element.closest('form'));
  }

  function isNavigatingAnchor(anchor) {
    return Boolean(anchor && !isSkippableAnchor(anchor));
  }

  function hasLocalUiHandler(element) {
    const inlineHandler = (element.getAttribute('onclick') || '').toLowerCase();
    return /\b(toggle|open|close|show|hide)[a-z0-9_]*\s*\(/.test(inlineHandler);
  }

  function isLocalUiControl(element, eventTarget) {
    if (!element) return false;
    if (hasNoLoadingOptOut(element) || eventTarget?.closest?.('[data-no-loading]')) return true;

    const anchor = element.closest('a');
    if (isNavigatingAnchor(anchor)) return false;

    const localSelectors = [
      '.hamburger',
      '.admin-hamburger',
      '.theme-toggle',
      '.admin-theme-toggle',
      '.lang-btn',
      '.lang-switcher',
      '.admin-lang-switcher',
      '.modal-close',
      '.google-forms-iframe-close',
      '.curriculum-toggle',
      '.toggle-password',
      '.scroll-top-btn',
      '.rich-editor-toolbar',
      '.rich-editor-btn',
      '.faq-arrow',
      '.dropdown-toggle',
      '.group-mode-close',
      '[data-section-target]',
      '[data-register-role]',
      '[data-student-next]',
      '[data-student-back]',
      '[data-student-org-mode]',
      '[data-google-forms-action]',
      '[data-announcement-edit]',
      '[data-group-mode-close]',
      '[aria-haspopup]',
      '[data-bs-toggle]',
      '[data-modal]',
      '[data-toggle]',
    ].join(',');

    if (element.closest(localSelectors) || eventTarget?.closest?.(localSelectors)) return true;

    if (
      (element.hasAttribute('aria-controls') || element.hasAttribute('aria-expanded')) &&
      !isSubmitControl(element)
    ) {
      return true;
    }

    return hasLocalUiHandler(element);
  }

  function isSkippableAnchor(anchor) {
    if (!anchor) return false;
    const hrefAttr = anchor.getAttribute('href') || '';
    const normalizedHref = hrefAttr.trim();

    if (!normalizedHref) return true;
    if (normalizedHref === '#') return true;
    if (anchor.target === '_blank') return true;
    if (anchor.hasAttribute('download')) return true;
    if (/^(mailto|tel):/i.test(normalizedHref)) return true;

    if (normalizedHref.startsWith('#')) return true;

    try {
      const url = new URL(normalizedHref, window.location.href);
      const samePageHash =
        url.origin === window.location.origin &&
        url.pathname === window.location.pathname &&
        url.search === window.location.search &&
        Boolean(url.hash);
      if (samePageHash) return true;
    } catch (_) {
      return true;
    }

    return false;
  }

  function shouldHandleClick(event, target) {
    if (!isMobileFeedbackEnabled()) return false;
    if (!target || event.defaultPrevented) return false;
    if (event.button !== 0) return false;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return false;
    if (isDisabled(target) || hasNoLoadingOptOut(target) || isFileInput(target)) return false;
    if (event.target?.closest?.('[data-no-loading]')) return false;
    if (isSubmitControl(target)) return false;
    if (isLocalUiControl(target, event.target)) return false;

    const anchor = target.closest('a');
    if (isSkippableAnchor(anchor)) return false;

    return true;
  }

  function maybeStartFromClick(event) {
    const target = event.target?.closest?.(CLICKABLE_SELECTOR);
    if (!target) return;

    if (!shouldHandleClick(event, target)) return;
    startFeedback();

    window.setTimeout(() => {
      if (event.defaultPrevented) {
        cancelFeedback();
        return;
      }
      if (fetchCount <= 0) {
        window.setTimeout(() => {
          if (fetchCount <= 0) finishFeedback();
        }, MIN_DURATION);
      }
    }, 0);
  }

  function maybeStartFromSubmit(event) {
    const form = event.target;
    const submitter = event.submitter;
    if (!form || hasNoLoadingOptOut(form) || (submitter && hasNoLoadingOptOut(submitter))) return;

    window.setTimeout(() => {
      if (!isMobileFeedbackEnabled() || event.defaultPrevented) return;
      startFeedback();
      if (fetchCount <= 0) {
        window.setTimeout(() => {
          if (fetchCount <= 0) finishFeedback();
        }, MIN_DURATION);
      }
    }, 0);
  }

  function wrapFetch() {
    if (!window.fetch || window.fetch.__mobileClickFeedbackWrapped) return;

    const nativeFetch = window.fetch.bind(window);
    function wrappedFetch() {
      if (!isMobileFeedbackEnabled()) {
        return nativeFetch.apply(null, arguments);
      }

      fetchCount += 1;
      startFeedback();

      let request;
      try {
        request = nativeFetch.apply(null, arguments);
      } catch (error) {
        fetchCount = Math.max(0, fetchCount - 1);
        if (fetchCount === 0) finishFeedback();
        throw error;
      }

      return Promise.resolve(request).finally(() => {
        fetchCount = Math.max(0, fetchCount - 1);
        if (fetchCount === 0) finishFeedback();
      });
    }

    wrappedFetch.__mobileClickFeedbackWrapped = true;
    window.fetch = wrappedFetch;
  }

  document.addEventListener('click', maybeStartFromClick, false);
  document.addEventListener('submit', maybeStartFromSubmit, false);

  window.addEventListener('pagehide', cancelFeedback);
  window.addEventListener('pageshow', cancelFeedback);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) cancelFeedback();
  });

  wrapFetch();
})();
