(function () {
  function translate(key, params = {}, fallback = "") {
    if (typeof window.t === "function") {
      return window.t(key, params);
    }
    return fallback || key;
  }

  function createAnswerRow(index) {
    const row = document.createElement("div");
    row.className = "answer-row";
    row.innerHTML = `
      <input type="text" name="answer_${index}" class="form-input"
             data-i18n="lesson.ans_ph"
             data-i18n-params='{"n": ${index}}'
             data-i18n-prop="placeholder"
             placeholder="${translate("lesson.ans_ph", { n: index }, `Вариант ${index}`)}" />
      <label><input type="checkbox" name="correct_${index}" />
      <span data-i18n="lesson.ans_correct"> ${translate("lesson.ans_correct", {}, "Правильный")}</span></label>
    `;
    return row;
  }

  function syncBuilder(root) {
    const typeField = root.querySelector("[data-quiz-question-type]");
    const answerOptions = root.querySelector("[data-quiz-answer-options]");
    const openField = root.querySelector("[data-quiz-open-answer-field]");
    const addButton = root.querySelector("[data-add-answer-row]");
    const hint = root.querySelector("[data-quiz-type-hint]");

    if (!typeField || !answerOptions || !openField) {
      return;
    }

    const isOpen = typeField.value === "open";

    answerOptions.hidden = isOpen;
    openField.hidden = !isOpen;
    if (addButton) addButton.hidden = isOpen;

    answerOptions.querySelectorAll("input").forEach((input) => {
      input.disabled = isOpen;
    });
    openField.querySelectorAll("input, textarea").forEach((input) => {
      input.disabled = !isOpen;
    });

    if (!hint) return;
    if (typeField.value === "single") {
      hint.textContent = translate("quiz.builder_hint_single", {}, "Отметьте ровно один правильный вариант.");
    } else if (typeField.value === "multiple") {
      hint.textContent = translate("quiz.builder_hint_multiple", {}, "Можно отметить несколько правильных вариантов.");
    } else {
      hint.textContent = translate("quiz.builder_hint_open", {}, "Студент введёт ответ вручную, сравнение будет без учёта регистра и лишних пробелов.");
    }
  }

  function validateBuilderForm(root) {
    const typeField = root.querySelector("[data-quiz-question-type]");
    const errorEl = root.querySelector("[data-quiz-builder-error]");
    const questionField = root.querySelector('input[name="question_text"]');
    const answerFields = Array.from(root.querySelectorAll('[data-quiz-answer-options] input[type="text"]'));
    const correctChecks = Array.from(root.querySelectorAll('[data-quiz-answer-options] input[type="checkbox"]'));
    const openField = root.querySelector('[name="correct_text"]');

    if (errorEl) errorEl.textContent = "";

    if (!questionField || !typeField) {
      return true;
    }

    if (!questionField.value.trim()) {
      if (errorEl) errorEl.textContent = translate("lesson.q_text", {}, "Текст вопроса обязателен");
      questionField.focus();
      return false;
    }

    if (typeField.value === "open") {
      if (!openField || !openField.value.trim()) {
        if (errorEl) errorEl.textContent = translate("lesson.correct_answer", {}, "Укажите правильный ответ");
        openField?.focus();
        return false;
      }
      return true;
    }

    const filledAnswers = answerFields
      .map((field, index) => ({ field, checked: !!correctChecks[index]?.checked }))
      .filter((item) => item.field.value.trim());

    if (filledAnswers.length < 2) {
      if (errorEl) errorEl.textContent = translate("quiz.validation_builder_answers", {}, "Добавьте минимум два варианта ответа.");
      answerFields[0]?.focus();
      return false;
    }

    const correctCount = filledAnswers.filter((item) => item.checked).length;
    if (typeField.value === "single" && correctCount !== 1) {
      if (errorEl) errorEl.textContent = translate("quiz.validation_builder_single", {}, "Для вопроса с одним ответом отметьте ровно один правильный вариант.");
      return false;
    }

    if (typeField.value === "multiple" && correctCount < 1) {
      if (errorEl) errorEl.textContent = translate("quiz.validation_builder_multiple", {}, "Для вопроса с несколькими ответами отметьте хотя бы один правильный вариант.");
      return false;
    }

    return true;
  }

  function initBuilder(root) {
    if (!root || root.dataset.quizBuilderReady === "1") {
      return;
    }
    root.dataset.quizBuilderReady = "1";

    const answerOptions = root.querySelector("[data-quiz-answer-options]");
    const addButton = root.querySelector("[data-add-answer-row]");
    const typeField = root.querySelector("[data-quiz-question-type]");
    const createToggle = root.querySelector("[data-quiz-create-toggle]");
    const createForm = root.querySelector("[data-quiz-create-form]");

    let answerCount = answerOptions ? answerOptions.querySelectorAll(".answer-row").length : 0;

    if (createToggle && createForm) {
      createToggle.addEventListener("click", () => {
        createForm.hidden = !createForm.hidden;
        createToggle.classList.toggle("is-active", !createForm.hidden);
        if (!createForm.hidden) {
          createForm.querySelector('input[name="title"]')?.focus();
        }
      });
    }

    if (addButton && answerOptions) {
      addButton.addEventListener("click", () => {
        answerCount += 1;
        const row = createAnswerRow(answerCount);
        answerOptions.appendChild(row);
        if (typeof window.setLang === "function") {
          window.setLang(localStorage.getItem("lang") || "tj");
        }
      });
    }

    if (typeField) {
      typeField.addEventListener("change", () => syncBuilder(root));
    }

    root.querySelectorAll(".quiz-question-form").forEach((form) => {
      form.addEventListener("submit", (event) => {
        if (!validateBuilderForm(root)) {
          event.preventDefault();
        }
      });
    });

    syncBuilder(root);
  }

  window.initQuizBuilders = function initQuizBuilders(scope = document) {
    scope.querySelectorAll("[data-quiz-builder-root]").forEach(initBuilder);
  };

  document.addEventListener("DOMContentLoaded", () => {
    window.initQuizBuilders(document);
  });
})();
