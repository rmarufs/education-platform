(function () {
  const TOOLBAR = [
    { command: "bold", icon: "B", titleKey: "editor.bold" },
    { command: "italic", icon: "I", titleKey: "editor.italic" },
    { command: "strikeThrough", icon: "S", titleKey: "editor.strike" },
    { type: "separator" },
    { command: "createLink", icon: "🔗", titleKey: "editor.link" },
    { command: "insertUnorderedList", icon: "•", titleKey: "editor.bullets" },
    { command: "insertOrderedList", icon: "1.", titleKey: "editor.numbered" },
    { type: "separator" },
    { command: "justifyLeft", icon: "≡", titleKey: "editor.align_left" },
    { command: "justifyCenter", icon: "≣", titleKey: "editor.align_center" },
    { command: "justifyRight", icon: "☰", titleKey: "editor.align_right" }
  ];

  let activeEditor = null;

  function normalizeHtml(html) {
    const trimmed = (html || "").trim();
    if (!trimmed || trimmed === "<br>" || trimmed === "<div><br></div>" || trimmed === "<p><br></p>") {
      return "";
    }
    return trimmed;
  }

  function getParts(wrapper) {
    return {
      input: wrapper.querySelector(".rich-editor-input"),
      surface: wrapper.querySelector(".rich-editor-surface"),
      toolbar: wrapper.querySelector(".rich-editor-toolbar"),
    };
  }

  function markEmpty(wrapper) {
    const { surface } = getParts(wrapper);
    if (!surface) return;
    const empty = !surface.textContent.trim() && !surface.querySelector("img,iframe,video,ul,ol,li,blockquote");
    surface.classList.toggle("is-empty", empty);
  }

  function syncWrapper(wrapper) {
    const { input, surface } = getParts(wrapper);
    if (!input || !surface) return;
    input.value = normalizeHtml(surface.innerHTML);
    markEmpty(wrapper);
  }

  function updateToolbarState(wrapper) {
    const { toolbar, surface } = getParts(wrapper);
    if (!toolbar || !surface) return;
    toolbar.querySelectorAll(".rich-editor-btn[data-command]").forEach((btn) => {
      const command = btn.dataset.command;
      let active = false;
      try {
        if (command.startsWith("justify")) {
          active = document.queryCommandState(command);
        } else if (command !== "createLink") {
          active = document.queryCommandState(command);
        }
      } catch (_) {
        active = false;
      }
      btn.classList.toggle("is-active", active);
    });
  }

  function focusEditor(wrapper) {
    const { surface } = getParts(wrapper);
    if (!surface) return;
    surface.focus();
    activeEditor = wrapper;
  }

  function execCommand(wrapper, command) {
    const { surface } = getParts(wrapper);
    if (!surface) return;
    focusEditor(wrapper);

    if (command === "createLink") {
      const url = window.prompt((window.t ? t("editor.link_prompt") : "Введите ссылку"), "https://");
      if (!url) return;
      document.execCommand("createLink", false, url.trim());
    } else {
      document.execCommand(command, false, null);
    }

    syncWrapper(wrapper);
    updateToolbarState(wrapper);
  }

  function buildToolbar(wrapper) {
    const toolbar = document.createElement("div");
    toolbar.className = "rich-editor-toolbar";

    TOOLBAR.forEach((item) => {
      if (item.type === "separator") {
        const separator = document.createElement("span");
        separator.className = "rich-editor-separator";
        toolbar.appendChild(separator);
        return;
      }

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "rich-editor-btn";
      btn.dataset.command = item.command;
      btn.dataset.i18n = item.titleKey;
      btn.dataset.i18nProp = "title";
      btn.setAttribute("title", window.t ? t(item.titleKey) : item.titleKey);
      btn.innerHTML = `<span>${item.icon}</span>`;
      btn.addEventListener("mousedown", (event) => event.preventDefault());
      btn.addEventListener("click", () => execCommand(wrapper, item.command));
      toolbar.appendChild(btn);
    });

    return toolbar;
  }

  function initWrapper(wrapper) {
    if (!wrapper || wrapper.dataset.rteReady === "true") return;
    const { surface, input } = getParts(wrapper);
    if (!surface || !input) return;

    const shell = wrapper.querySelector(".rich-editor-shell");
    if (shell && !wrapper.querySelector(".rich-editor-toolbar")) {
      shell.prepend(buildToolbar(wrapper));
    }

    surface.addEventListener("focus", () => {
      activeEditor = wrapper;
      wrapper.classList.add("is-focused");
      updateToolbarState(wrapper);
    });

    surface.addEventListener("blur", () => {
      wrapper.classList.remove("is-focused");
      syncWrapper(wrapper);
    });

    surface.addEventListener("input", () => syncWrapper(wrapper));
    surface.addEventListener("keyup", () => updateToolbarState(wrapper));
    surface.addEventListener("mouseup", () => updateToolbarState(wrapper));

    wrapper.closest("form")?.addEventListener("submit", () => syncWrapper(wrapper));

    wrapper.dataset.rteReady = "true";
    syncWrapper(wrapper);
  }

  window.initRichTextEditors = function (scope = document) {
    scope.querySelectorAll(".rich-editor").forEach(initWrapper);
  };

  window.setRichTextValue = function (inputId, html = "") {
    const input = document.getElementById(inputId);
    if (!input) return;
    input.value = html || "";
    const wrapper = input.closest(".rich-editor");
    const surface = wrapper?.querySelector(".rich-editor-surface");
    if (!surface) return;
    surface.innerHTML = html || "";
    syncWrapper(wrapper);
    updateToolbarState(wrapper);
  };

  window.refreshRichTextToolbars = function () {
    document.querySelectorAll(".rich-editor-btn[data-i18n]").forEach((btn) => {
      const key = btn.getAttribute("data-i18n");
      if (!key || !window.t) return;
      btn.setAttribute("title", t(key));
    });
  };

  document.addEventListener("selectionchange", () => {
    if (activeEditor) updateToolbarState(activeEditor);
  });

  document.addEventListener("DOMContentLoaded", () => {
    window.initRichTextEditors();
    window.refreshRichTextToolbars();
  });
})();
