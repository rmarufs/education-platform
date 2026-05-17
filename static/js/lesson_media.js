(function () {
  function getParts(root) {
    return {
      videoField: root.querySelector("[data-lesson-video-field]"),
      videoInput: root.querySelector("[data-lesson-video-input]"),
      coverField: root.querySelector("[data-lesson-cover-field]"),
      coverInput: root.querySelector("[data-lesson-cover-input]"),
      coverRemove: root.querySelector("[data-lesson-cover-remove]"),
      coverPreview: root.querySelector("[data-lesson-cover-preview]"),
      coverRemoveBtn: root.querySelector("[data-lesson-cover-remove-btn]"),
      dropzone: root.querySelector("[data-lesson-cover-dropzone]"),
    };
  }

  function hasSelectedCover(coverInput) {
    return Boolean(coverInput?.files && coverInput.files.length > 0);
  }

  function setPreview(root, src) {
    const { coverPreview } = getParts(root);
    if (!coverPreview) return;
    if (src) {
      coverPreview.src = src;
      coverPreview.hidden = false;
    } else {
      coverPreview.removeAttribute("src");
      coverPreview.hidden = true;
    }
  }

  function sync(root) {
    const {
      videoField,
      videoInput,
      coverField,
      coverInput,
      coverRemove,
      coverRemoveBtn,
    } = getParts(root);

    if (!videoInput || !coverInput || !videoField || !coverField) return;

    const hasVideo = Boolean(videoInput.value.trim());
    const hasFile = hasSelectedCover(coverInput);
    const hasCurrentCover = Boolean(root.dataset.currentCover);
    const hasCover = hasFile || hasCurrentCover;

    if (hasVideo) {
      coverField.hidden = true;
      coverInput.disabled = true;
      if (coverRemove) coverRemove.value = hasCurrentCover ? "1" : "0";
      if (coverRemoveBtn) coverRemoveBtn.hidden = true;
      return;
    }

    coverField.hidden = false;
    coverInput.disabled = false;

    if (hasCover) {
      videoField.hidden = true;
      videoInput.disabled = true;
      if (coverRemove) coverRemove.value = "0";
      if (coverRemoveBtn) coverRemoveBtn.hidden = false;
      if (hasCurrentCover && !hasFile) setPreview(root, root.dataset.currentCover);
      return;
    }

    videoField.hidden = false;
    videoInput.disabled = false;
    if (coverRemove && coverRemove.value !== "1") coverRemove.value = "0";
    if (coverRemoveBtn) coverRemoveBtn.hidden = true;
    setPreview(root, "");
  }

  function selectCover(root, fileList) {
    const { coverInput } = getParts(root);
    if (!coverInput || !fileList || !fileList.length) return;

    try {
      const transfer = new DataTransfer();
      transfer.items.add(fileList[0]);
      coverInput.files = transfer.files;
    } catch (_) {
      return;
    }

    root.dataset.currentCover = "";
    setPreview(root, URL.createObjectURL(fileList[0]));
    sync(root);
  }

  function bind(root) {
    if (!root || root.dataset.lessonMediaReady === "1") return;
    const { videoInput, coverInput, coverRemoveBtn, dropzone } = getParts(root);
    if (!videoInput || !coverInput) return;

    videoInput.addEventListener("input", () => sync(root));
    coverInput.addEventListener("change", () => {
      root.dataset.currentCover = "";
      const file = coverInput.files?.[0];
      setPreview(root, file ? URL.createObjectURL(file) : "");
      sync(root);
    });

    coverRemoveBtn?.addEventListener("click", () => {
      const { coverRemove } = getParts(root);
      coverInput.value = "";
      root.dataset.currentCover = "";
      if (coverRemove) coverRemove.value = "1";
      setPreview(root, "");
      sync(root);
    });

    dropzone?.addEventListener("dragover", (event) => {
      event.preventDefault();
      dropzone.classList.add("is-dragover");
    });
    dropzone?.addEventListener("dragleave", () => dropzone.classList.remove("is-dragover"));
    dropzone?.addEventListener("drop", (event) => {
      event.preventDefault();
      dropzone.classList.remove("is-dragover");
      selectCover(root, event.dataTransfer?.files);
    });

    root.closest("form")?.addEventListener("submit", (event) => {
      const { videoInput: currentVideo, coverInput: currentCover } = getParts(root);
      if (currentVideo?.value.trim() && hasSelectedCover(currentCover)) {
        event.preventDefault();
        alert(window.t ? t("lesson.media_conflict_error") : "Можно добавить либо видео, либо картинку");
      }
    });

    root.dataset.lessonMediaReady = "1";
    sync(root);
  }

  window.initLessonMediaEditors = function (scope = document) {
    scope.querySelectorAll("[data-lesson-media-editor]").forEach(bind);
  };

  window.resetLessonMediaEditor = function (root, currentCover = "") {
    if (!root) return;
    bind(root);
    const { coverInput, coverRemove } = getParts(root);
    if (coverInput) coverInput.value = "";
    if (coverRemove) coverRemove.value = "0";
    root.dataset.currentCover = currentCover || "";
    setPreview(root, currentCover || "");
    sync(root);
  };

  document.addEventListener("DOMContentLoaded", () => window.initLessonMediaEditors());
})();
