let currentIndex = EXISTING_ANSWERS ? EXISTING_ANSWERS.length : 0;
const answers = EXISTING_ANSWERS ? [...EXISTING_ANSWERS] : [];
const VOCAB_ANTICHEAT_MIN_AWAY_MS = 900;
let vocabAwaySession = null;
let vocabAwayTimer = null;
let vocabFocusLossCount = 0;
let vocabIsLeavingPage = false;
let vocabAntiCheatSecondReported = false;

// \u0422\u0430\u0434\u0436\u0438\u043a\u0441\u043a\u0438\u0435 \u044d\u043a\u0432\u0438\u0432\u0430\u043b\u0435\u043d\u0442\u044b: \u043e\u0431\u0435 \u0441\u0442\u043e\u0440\u043e\u043d\u044b (tj-\u0431\u0443\u043a\u0432\u0430 \u2192 \u0440\u0443\u0441\u0441\u043a\u0430\u044f \u0438 \u043d\u0430\u043e\u0431\u043e\u0440\u043e\u0442)
const TJ_EQUIV = [
  ['\u04e3', '\u0438'],  // \u04e3 \u2194 \u0438
  ['\u04ef', '\u0443'],  // \u04ef \u2194 \u0443
  ['\u0493', '\u0433'],  // \u0493 \u2194 \u0433
  ['\u049b', '\u043a'],  // \u049b \u2194 \u043a
  ['\u04b3', '\u0445'],  // \u04b3 \u2194 \u0445
  ['\u04b7', '\u0447'],  // \u04b7 \u2194 \u0447
];

function normalizeTajik(str) {
  let s = str;
  for (const [tj, ru] of TJ_EQUIV) {
    // \u0417\u0430\u043c\u0435\u043d\u044f\u0435\u043c \u043e\u0431\u0430 \u043d\u0430\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u044f \u043d\u0430 ru-\u0432\u0430\u0440\u0438\u0430\u043d\u0442 (\u043a\u0430\u043d\u043e\u043d\u0438\u0437\u0430\u0446\u0438\u044f \u043a \u043e\u0434\u043d\u043e\u043c\u0443 \u044f\u0437\u044b\u043a\u0443)
    s = s.replaceAll(tj, ru).replaceAll(tj.toUpperCase(), ru.toUpperCase());
  }
  return s;
}

function normalizeAnswer(str) {
  if (!str) return '';
  return normalizeTajik(
    str.toLowerCase().trim()
      .replace(/\s+/g, ' ')
      .replace(/[.,!?;:'"«»""]+$/g, '')
      .replace(/\u0451/g, '\u0435')  // \u0451 \u2192 \u0435
  );
}

function getAcceptedAnswers(item) {
  let source = '';
  if (CURRENT_LANG === 'ru' && item.accepted_answers_ru) source = item.accepted_answers_ru;
  else if (CURRENT_LANG === 'tj' && item.accepted_answers_tj) source = item.accepted_answers_tj;
  else source = item.accepted_answers || '';
  return source.split('|').map(a => a.trim()).filter(Boolean);
}

function isVocabAttemptActive() {
  return Boolean(ATTEMPT_ID) && !vocabIsLeavingPage && currentIndex < VOCAB_ITEMS.length;
}

function setVocabLeavingPage() {
  vocabIsLeavingPage = true;
  clearVocabAwayTimer();
}

function clearVocabAwayTimer() {
  if (vocabAwayTimer) {
    clearTimeout(vocabAwayTimer);
    vocabAwayTimer = null;
  }
}

function isPageAway() {
  return document.hidden || !document.hasFocus();
}

function showVocabAntiCheatNotice(count) {
  const notice = document.getElementById('vocab-anticheat-notice');
  const titleEl = document.getElementById('vocab-anticheat-title');
  const messageEl = document.getElementById('vocab-anticheat-message');
  if (!notice || !titleEl || !messageEl) return;

  const isDanger = count >= 2;
  notice.classList.toggle('is-danger', isDanger);
  notice.classList.add('is-visible');
  notice.setAttribute('aria-hidden', 'false');
  titleEl.textContent = t(isDanger ? 'vocabulary.anticheat_danger_title' : 'vocabulary.anticheat_warning_title');
  messageEl.textContent = t(isDanger ? 'vocabulary.anticheat_danger_message' : 'vocabulary.anticheat_warning_message');
}

async function reportVocabAntiCheatSecondWarning() {
  if (!VOCAB_ANTICHEAT_SECOND_WARNING_URL || vocabAntiCheatSecondReported) return;

  vocabAntiCheatSecondReported = true;
  try {
    await fetch(VOCAB_ANTICHEAT_SECOND_WARNING_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
  } catch (e) {
    // Quiz flow must continue even if the anti-cheat report cannot be saved.
  }
}

function recordVocabFocusLoss() {
  if (!isVocabAttemptActive() || !vocabAwaySession || vocabAwaySession.counted) return;

  vocabAwaySession.counted = true;
  vocabFocusLossCount++;
  showVocabAntiCheatNotice(vocabFocusLossCount);
  if (vocabFocusLossCount === 2) {
    reportVocabAntiCheatSecondWarning();
  }
}

function startVocabAwayTracking() {
  if (!isVocabAttemptActive() || vocabAwaySession) return;

  vocabAwaySession = {
    startedAt: Date.now(),
    counted: false,
  };
  clearVocabAwayTimer();
  vocabAwayTimer = setTimeout(() => {
    if (!vocabIsLeavingPage && isPageAway()) recordVocabFocusLoss();
  }, VOCAB_ANTICHEAT_MIN_AWAY_MS);
}

function finishVocabAwayTracking() {
  if (!vocabAwaySession) return;

  const duration = Date.now() - vocabAwaySession.startedAt;
  if (!vocabAwaySession.counted && duration >= VOCAB_ANTICHEAT_MIN_AWAY_MS && !vocabIsLeavingPage) {
    recordVocabFocusLoss();
  }
  clearVocabAwayTimer();
  vocabAwaySession = null;
}

function showWord(index) {
  const item = VOCAB_ITEMS[index];
  document.getElementById('vocab-word-display').textContent = item.prompt_word;
  document.getElementById('vocab-answer-input').value = '';
  document.getElementById('vocab-counter').textContent = (index + 1) + ' / ' + VOCAB_ITEMS.length;
  document.getElementById('vocab-progress-bar').style.width = (index / VOCAB_ITEMS.length * 100) + '%';
  document.getElementById('vocab-card').className = 'vocab-card';
  document.getElementById('vocab-screen-word').style.display = 'flex';
  document.getElementById('vocab-screen-result').style.display = 'none';
  setTimeout(() => { const inp = document.getElementById('vocab-answer-input'); if (inp) inp.focus(); }, 100);
}

function checkAnswer() {
  const input = document.getElementById('vocab-answer-input');
  const userAnswer = (input.value || '').trim();
  if (!userAnswer) {
    input.classList.add('shake');
    setTimeout(() => input.classList.remove('shake'), 500);
    input.focus();
    return;
  }
  const item = VOCAB_ITEMS[currentIndex];
  const accepted = getAcceptedAnswers(item);
  const isCorrect = accepted.some(a => normalizeAnswer(a) === normalizeAnswer(userAnswer));
  showResult(item, userAnswer, isCorrect, accepted, false);
}

function skipWord() {
  const item = VOCAB_ITEMS[currentIndex];
  const accepted = getAcceptedAnswers(item);
  showResult(item, '', false, accepted, true);
}

async function showResult(item, userAnswer, isCorrect, accepted, skipped) {
  const card = document.getElementById('vocab-card');
  document.getElementById('vocab-result-icon').textContent = skipped ? '\u23ed' : (isCorrect ? '\u2705' : '\u274c');
  const statusEl = document.getElementById('vocab-result-status');
  if (skipped) { statusEl.textContent = t('vocabulary.skipped'); statusEl.style.color = 'var(--text-muted)'; }
  else if (isCorrect) { statusEl.textContent = t('vocabulary.correct'); statusEl.style.color = '#22c55e'; }
  else { statusEl.textContent = t('vocabulary.wrong'); statusEl.style.color = 'var(--error, #ef4444)'; }
  document.getElementById('vocab-result-word-display').textContent = item.prompt_word;
  document.getElementById('vocab-user-answer-display').textContent = userAnswer || '\u2014';
  document.getElementById('vocab-correct-answer-display').textContent = accepted.join(' / ');
  document.getElementById('vocab-correct-row').style.display = (skipped || !isCorrect) ? 'flex' : 'none';
  document.getElementById('vocab-screen-word').style.display = 'none';
  document.getElementById('vocab-screen-result').style.display = 'flex';

  answers.push({ item_id: item.id, student_answer: userAnswer, is_correct: isCorrect });
  
  if (VOCAB_SUBMIT_ANSWER_URL) {
    try {
      await fetch(VOCAB_SUBMIT_ANSWER_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: item.id, student_answer: userAnswer, is_correct: isCorrect, lang: CURRENT_LANG }),
      });
    } catch (e) {
      console.error("Failed to save answer", e);
    }
  }
}

function nextWord() {
  currentIndex++;
  if (currentIndex >= VOCAB_ITEMS.length) {
    submitResults();
  } else {
    showWord(currentIndex);
  }
}

async function submitResults() {
  setVocabLeavingPage();
  document.getElementById('vocab-progress-bar').style.width = '100%';
  if (!VOCAB_COMPLETE_URL) {
    window.location.href = VOCAB_RESULT_URL;
    return;
  }
  try {
    const resp = await fetch(VOCAB_COMPLETE_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    if (resp.status === 409) {
      // Уже проходил, повтор запрещён
      window.location.href = VOCAB_RESULT_URL;
      return;
    }
    if (!resp.ok) throw new Error();
    const data = await resp.json();
    window.location.href = VOCAB_RESULT_URL + '?score=' + data.score + '&total=' + data.total;
  } catch (e) {
    window.location.href = VOCAB_RESULT_URL;
  }
}

async function confirmQuit(e) {
  e.preventDefault();
  if (answers.length === 0 || await showConfirmModal(t('vocabulary.quit_confirm'))) {
    setVocabLeavingPage();
    window.location.href = VOCAB_BACK_URL;
  }
  return false;
}

document.addEventListener('DOMContentLoaded', () => {
  const antiCheatCloseBtn = document.getElementById('vocab-anticheat-close');
  if (antiCheatCloseBtn) {
    antiCheatCloseBtn.addEventListener('click', () => {
      const notice = document.getElementById('vocab-anticheat-notice');
      if (notice) {
        notice.classList.remove('is-visible');
        notice.setAttribute('aria-hidden', 'true');
      }
    });
  }

  if (!VOCAB_ITEMS.length) {
    document.getElementById('vocab-quiz-wrap').innerHTML = `<p style="text-align:center;padding:40px;" data-i18n="vocabulary.no_words">${t('vocabulary.no_words')}</p>`;
    return;
  }
  if (currentIndex >= VOCAB_ITEMS.length) {
    submitResults();
    return;
  }
  showWord(currentIndex);
  document.getElementById('vocab-answer-input').addEventListener('keydown', (e) => { if (e.key === 'Enter') checkAnswer(); });
});

document.addEventListener('visibilitychange', () => {
  if (document.hidden) startVocabAwayTracking();
  else finishVocabAwayTracking();
});

window.addEventListener('blur', startVocabAwayTracking);
window.addEventListener('focus', finishVocabAwayTracking);
window.addEventListener('beforeunload', setVocabLeavingPage);
