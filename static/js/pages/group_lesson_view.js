document.addEventListener("DOMContentLoaded", () => {
  const layout = document.getElementById("lesson-layout");
  const toggle = document.getElementById("lesson-sidebar-toggle");
  const overlay = document.getElementById("lesson-sidebar-overlay");
  const closeBtn = document.getElementById("lesson-sidebar-close");
  const desktopMq = window.matchMedia("(min-width: 769px)");
  if (!layout || !toggle || !overlay) return;

  function setPageScrollLocked(locked) {
    const isLocked = document.body.classList.contains("lesson-sidebar-open");
    if (locked === isLocked) return;

    if (locked) {
      const scrollY = window.scrollY || document.documentElement.scrollTop || 0;
      document.body.dataset.lessonScrollY = String(scrollY);
      document.body.classList.add("lesson-sidebar-open");
      document.body.style.position = "fixed";
      document.body.style.top = `-${scrollY}px`;
      document.body.style.left = "0";
      document.body.style.right = "0";
      document.body.style.width = "100%";
      return;
    }

    const scrollY = Number.parseInt(document.body.dataset.lessonScrollY || "0", 10) || 0;
    document.body.classList.remove("lesson-sidebar-open");
    document.body.style.position = "";
    document.body.style.top = "";
    document.body.style.left = "";
    document.body.style.right = "";
    document.body.style.width = "";
    delete document.body.dataset.lessonScrollY;
    window.scrollTo(0, scrollY);
  }

  function setSidebarOpen(open) {
    layout.classList.toggle("sidebar-open", open);
    if (desktopMq.matches) {
      setPageScrollLocked(false);
    } else {
      setPageScrollLocked(open);
    }
    toggle.setAttribute("aria-expanded", String(open));
  }

  toggle.addEventListener("click", () => setSidebarOpen(!layout.classList.contains("sidebar-open")));
  if (closeBtn) closeBtn.addEventListener("click", () => setSidebarOpen(false));
  overlay.addEventListener("click", () => setSidebarOpen(false));
  window.addEventListener("resize", () => {
    if (desktopMq.matches) {
      setPageScrollLocked(false);
    }
  });
  window.addEventListener("pagehide", () => setPageScrollLocked(false));

  document.querySelectorAll("[data-vocab-anticheat-card]").forEach((card) => {
    const attemptId = card.getAttribute("data-attempt-id");
    if (!attemptId) return;
    const storageKey = `vocabTeacherAntiCheatDismissed:${attemptId}`;
    try {
      if (window.localStorage?.getItem(storageKey) === "1") {
        card.hidden = true;
      }
    } catch (_) {}
  });

  document.querySelectorAll("[data-vocab-anticheat-close]").forEach((button) => {
    button.addEventListener("click", () => {
      const card = button.closest("[data-vocab-anticheat-card]");
      if (!card) return;
      const attemptId = card.getAttribute("data-attempt-id");
      card.hidden = true;
      if (!attemptId) return;
      try {
        window.localStorage?.setItem(`vocabTeacherAntiCheatDismissed:${attemptId}`, "1");
      } catch (_) {}
    });
  });

  document.querySelectorAll(".group-lesson-complete-nav-form").forEach((form) => {
    form.addEventListener("submit", () => {
      const button = form.querySelector("button[type='submit']");
      if (button) button.disabled = true;
    });
  });

  // ── Mobile accordion: Материалы / Домашнее задание ──────────────────
  (function initGlMobAccordion() {
    const accordion = document.getElementById("gl-mob-accordion");
    if (!accordion) return;

    const tabs = accordion.querySelectorAll("[data-gl-mob-tab]");
    if (!tabs.length) return;

    tabs.forEach(function(tab) {
      tab.addEventListener("click", function() {
        const panelWrapId = tab.getAttribute("aria-controls");
        const panelWrap = panelWrapId ? document.getElementById(panelWrapId) : null;
        if (!panelWrap) return;

        const isOpen = tab.getAttribute("aria-expanded") === "true";

        if (isOpen) {
          // Закрыть эту же панель
          tab.setAttribute("aria-expanded", "false");
          panelWrap.classList.remove("is-open");
        } else {
          // Раскрыть эту панель, закрыть все остальные
          tabs.forEach(function(otherTab) {
            const otherId = otherTab.getAttribute("aria-controls");
            const otherWrap = otherId ? document.getElementById(otherId) : null;
            otherTab.setAttribute("aria-expanded", "false");
            if (otherWrap) otherWrap.classList.remove("is-open");
          });
          tab.setAttribute("aria-expanded", "true");
          panelWrap.classList.add("is-open");
        }
      });
    });
  })();
  // ─────────────────────────────────────────────────────────────────────────

});
