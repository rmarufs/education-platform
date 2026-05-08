/**
 * Фурузон — HTML5 Video Player (iOS/WebKit-stable)
 * Архитектура: videoLayer (чистый) + uiLayer (контролы) + fullscreenManager
 *
 * iOS edge cases закрыты:
 *  - video.webkitEnterFullscreen() → нативный FS на iPhone
 *  - playsinline + webkit-playsinline → inline воспроизведение
 *  - orientationchange + 300ms timeout → пересчёт layout
 *  - env(safe-area-inset-*) → notch/Dynamic Island
 *  - object-fit: contain → нет обрезания в landscape
 *  - НЕТ backdrop-filter на overlay → нет артефактов Chrome iOS
 */
(function () {
  'use strict';

  /* ── Утилиты ─────────────────────────────────────────────── */
  function fmt(s) {
    if (isNaN(s) || s < 0) s = 0;
    s = Math.round(s);
    var m = Math.floor(s / 60);
    var sec = s % 60;
    return m + ':' + (sec < 10 ? '0' : '') + sec;
  }

  function debounce(fn, ms) {
    var t;
    return function () { clearTimeout(t); t = setTimeout(fn, ms); };
  }

  /* ── Определение iOS ─────────────────────────────────────── */
  var isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
  var isIOSSafari = isIOS && !/CriOS|FxiOS|OPiOS|EdgiOS/.test(navigator.userAgent);

  /* ══════════════════════════════════════════════════════════
     VideoPlayer — главный класс
     ══════════════════════════════════════════════════════════ */
  function VideoPlayer(shell) {
    this.shell      = shell;
    this.video      = shell.querySelector('.vp-video');
    this.overlay    = shell.querySelector('.vp-overlay');
    this.bigPlay    = shell.querySelector('.vp-big-play');
    this.controls   = shell.querySelector('.vp-controls');
    this.playBtn    = shell.querySelector('#vp-play-btn');
    this.muteBtn    = shell.querySelector('#vp-mute-btn');
    this.fsBtn      = shell.querySelector('#vp-fs-btn');
    this.progressEl = shell.querySelector('.vp-progress');
    this.fillEl     = shell.querySelector('.vp-progress-fill');
    this.handleEl   = shell.querySelector('.vp-progress-handle');
    this.timeEl     = shell.querySelector('.vp-time');
    this.speedBtn   = shell.querySelector('#vp-speed-btn');
    this.speedMenu  = shell.querySelector('.vp-speed-menu');
    this.watermark  = shell.querySelector('.vp-watermark');
    this.spinner    = shell.querySelector('.vp-spinner');

    // Состояние
    this.isPlaying     = false;
    this.isSeeking     = false;
    this.isMuted       = false;
    this.isPseudoFS    = false;
    this.currentRate   = 1;
    this.controlsTimer = null;
    this.seekPercent   = 0;
    this.progressInterval = null;

    this._bindEvents();
    this._initWatermark();
  }

  /* ── Привязка событий ────────────────────────────────────── */
  VideoPlayer.prototype._bindEvents = function () {
    var self = this;
    var v    = this.video;

    // Video events
    v.addEventListener('play',     function () { self._onPlay(); });
    v.addEventListener('pause',    function () { self._onPause(); });
    v.addEventListener('ended',    function () { self._onPause(); });
    v.addEventListener('waiting',  function () { self.shell.classList.add('vp-loading'); });
    v.addEventListener('canplay',  function () { self.shell.classList.remove('vp-loading'); });
    v.addEventListener('timeupdate', function () { if (!self.isSeeking) self._updateProgress(); });
    v.addEventListener('error',    function () { self.shell.classList.add('vp-error-state'); });

    // Fullscreen events (нативный)
    ['webkitendfullscreen', 'webkitbeginfullscreen'].forEach(function (ev) {
      v.addEventListener(ev, function () { self._syncFSState(); });
    });
    ['fullscreenchange', 'webkitfullscreenchange'].forEach(function (ev) {
      document.addEventListener(ev, function () { self._syncFSState(); });
    });

    // Кнопки
    this.playBtn  && this.playBtn.addEventListener('click', function (e) { e.stopPropagation(); self.togglePlay(); });
    this.muteBtn  && this.muteBtn.addEventListener('click', function (e) { e.stopPropagation(); self.toggleMute(); });
    this.fsBtn    && this.fsBtn.addEventListener('click', function (e) { e.stopPropagation(); self.toggleFullscreen(); });
    this.speedBtn && this.speedBtn.addEventListener('click', function (e) { e.stopPropagation(); self._toggleSpeedMenu(); });

    // Speed options
    this.shell.querySelectorAll('.vp-speed-opt').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        self.setRate(parseFloat(btn.getAttribute('data-rate')));
      });
    });

    // Клик вне speed menu
    document.addEventListener('click', function (e) {
      if (self.speedMenu && !self.speedMenu.contains(e.target) && e.target !== self.speedBtn) {
        self.speedMenu.classList.remove('vp-speed-open');
      }
    });

    // Overlay — play/pause + мобильные жесты
    this.overlay && this._bindOverlay();

    // Progress / Seek
    this.progressEl && this._bindSeek();

    // Ориентация экрана
    window.addEventListener('orientationchange', function () {
      setTimeout(function () { self._recalcLayout(); }, 300);
    });
    window.addEventListener('resize', debounce(function () { self._recalcLayout(); }, 150));

    // ESC выход из pseudo-FS
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && self.isPseudoFS) self._exitPseudoFS();
    });

    // Водяной знак
    this._moveWatermark();
    this._wmInterval = setInterval(function () { self._moveWatermark(); }, 30000);
  };

  /* ── Play / Pause ────────────────────────────────────────── */
  VideoPlayer.prototype.togglePlay = function () {
    if (this.video.paused) {
      this.video.play().catch(function () {});
    } else {
      this.video.pause();
    }
  };

  VideoPlayer.prototype._onPlay = function () {
    this.isPlaying = true;
    this.shell.classList.add('vp-playing');
    this.playBtn && (this.playBtn.textContent = '⏸');
    this._resetControlsTimer();
    clearInterval(this.progressInterval);
    this.progressInterval = setInterval(this._updateProgress.bind(this), 250);
  };

  VideoPlayer.prototype._onPause = function () {
    this.isPlaying = false;
    this.shell.classList.remove('vp-playing');
    this.playBtn && (this.playBtn.textContent = '▶');
    clearTimeout(this.controlsTimer);
    clearInterval(this.progressInterval);
    this.shell.classList.remove('vp-controls-hidden');
  };

  /* ── Mute ────────────────────────────────────────────────── */
  VideoPlayer.prototype.toggleMute = function () {
    this.video.muted = !this.video.muted;
    this.isMuted = this.video.muted;
    this.muteBtn && (this.muteBtn.textContent = this.isMuted ? '🔇' : '🔊');
  };

  /* ── Speed ───────────────────────────────────────────────── */
  VideoPlayer.prototype.setRate = function (rate) {
    this.video.playbackRate = rate;
    this.currentRate = rate;
    this.speedBtn && (this.speedBtn.textContent = rate === 1 ? '1x' : rate + 'x');
    this.shell.querySelectorAll('.vp-speed-opt').forEach(function (btn) {
      btn.classList.toggle('vp-speed-active', parseFloat(btn.getAttribute('data-rate')) === rate);
    });
    this.speedMenu && this.speedMenu.classList.remove('vp-speed-open');
  };

  VideoPlayer.prototype._toggleSpeedMenu = function () {
    this.speedMenu && this.speedMenu.classList.toggle('vp-speed-open');
  };

  /* ── Progress / Seek ─────────────────────────────────────── */
  VideoPlayer.prototype._updateProgress = function () {
    if (this.isSeeking) return;
    var dur = this.video.duration || 0;
    var cur = this.video.currentTime || 0;
    var pct = dur > 0 ? (cur / dur) * 100 : 0;
    this._setProgressVisual(pct, cur, dur);
  };

  VideoPlayer.prototype._setProgressVisual = function (pct, cur, dur) {
    pct = Math.max(0, Math.min(100, pct || 0));
    if (this.fillEl)   this.fillEl.style.width = pct + '%';
    if (this.progressEl) this.progressEl.style.setProperty('--vp-progress', pct + '%');
    if (this.handleEl) this.handleEl.style.left = pct + '%';
    if (this.timeEl && typeof cur === 'number' && typeof dur === 'number') {
      this.timeEl.textContent = fmt(cur) + ' / ' + fmt(dur);
    }
  };

  VideoPlayer.prototype._bindSeek = function () {
    var self = this;
    var el   = this.progressEl;

    function getPct(e) {
      var pt = e.touches ? e.touches[0] : (e.changedTouches ? e.changedTouches[0] : e);
      var rect = el.getBoundingClientRect();
      if (!rect.width) return 0;
      return Math.max(0, Math.min(1, (pt.clientX - rect.left) / rect.width));
    }

    function onStart(e) {
      if (e.button && e.button !== 0) return;
      e.preventDefault();
      e.stopPropagation();
      self.isSeeking = true;
      self.shell.classList.add('vp-seeking');
      var pct = getPct(e);
      self.seekPercent = pct;
      self._setProgressVisual(pct * 100, pct * (self.video.duration || 0), self.video.duration || 0);
    }

    function onMove(e) {
      if (!self.isSeeking) return;
      e.preventDefault();
      var pct = getPct(e);
      self.seekPercent = pct;
      self._setProgressVisual(pct * 100, pct * (self.video.duration || 0), self.video.duration || 0);
    }

    function onEnd(e) {
      if (!self.isSeeking) return;
      e.preventDefault();
      var dur = self.video.duration || 0;
      if (dur > 0) self.video.currentTime = self.seekPercent * dur;
      self.isSeeking = false;
      self.shell.classList.remove('vp-seeking');
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onEnd);
      document.removeEventListener('touchmove', onMove);
      document.removeEventListener('touchend', onEnd);
    }

    el.addEventListener('mousedown', function (e) {
      onStart(e);
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onEnd);
    });

    el.addEventListener('touchstart', function (e) {
      onStart(e);
      document.addEventListener('touchmove', onMove, { passive: false });
      document.addEventListener('touchend', onEnd);
    }, { passive: false });
  };

  /* ── Controls auto-hide ──────────────────────────────────── */
  VideoPlayer.prototype._resetControlsTimer = function () {
    var self = this;
    this.shell.classList.remove('vp-controls-hidden');
    clearTimeout(this.controlsTimer);
    if (this.isPlaying) {
      this.controlsTimer = setTimeout(function () {
        self.shell.classList.add('vp-controls-hidden');
      }, 3000);
    }
  };

  /* ── Touch overlay (мобильные жесты) ────────────────────── */
  VideoPlayer.prototype._bindOverlay = function () {
    var self      = this;
    var overlay   = this.overlay;
    var startX, startY, startTime, lastTap = 0, lastTapX = 0;
    var SWIPE_THR   = 50;
    var DOUBLE_MS   = 280;

    overlay.addEventListener('touchstart', function (e) {
      startX    = e.touches[0].clientX;
      startY    = e.touches[0].clientY;
      startTime = Date.now();
    }, { passive: true });

    overlay.addEventListener('touchend', function (e) {
      var t  = e.changedTouches[0];
      var dx = t.clientX - startX;
      var dy = t.clientY - startY;
      var dt = Date.now() - startTime;

      // Вертикальный скролл — игнорируем
      if (Math.abs(dy) > 30 && Math.abs(dy) > Math.abs(dx)) {
        self._resetControlsTimer(); return;
      }

      // Swipe: перемотка ±10 сек
      if (Math.abs(dx) > SWIPE_THR && dt < 400 && Math.abs(dy) < 40) {
        var newTime = Math.max(0, self.video.currentTime + (dx > 0 ? 10 : -10));
        self.video.currentTime = Math.min(newTime, self.video.duration || newTime);
        self._showRipple(dx > 0, 10);
        self._resetControlsTimer();
        return;
      }

      // Tap / Double tap
      if (Math.abs(dx) < 16 && Math.abs(dy) < 16 && dt < 260) {
        var now    = Date.now();
        var rect   = self.shell.getBoundingClientRect();
        var relX   = (t.clientX - rect.left) / rect.width;
        var isDouble = (now - lastTap < DOUBLE_MS) && (Math.abs(t.clientX - lastTapX) < 64);

        if (isDouble) {
          if (relX < 0.3) {
            self.video.currentTime = Math.max(0, self.video.currentTime - 10);
            self._showRipple(false, 10);
          } else if (relX > 0.7) {
            self.video.currentTime = Math.min(self.video.duration || Infinity, self.video.currentTime + 10);
            self._showRipple(true, 10);
          } else {
            self.togglePlay();
          }
          lastTap = 0;
          self._resetControlsTimer();
          return;
        }

        lastTap  = now;
        lastTapX = t.clientX;

        if (self.shell.classList.contains('vp-controls-hidden')) {
          self._resetControlsTimer();
        } else {
          self.togglePlay();
          self._resetControlsTimer();
        }
      }
    }, { passive: true });

    // Касание controls — сброс таймера
    this.controls && this.controls.addEventListener('touchstart', function () {
      self._resetControlsTimer();
    }, { passive: true });
  };

  /* ── Seek ripple ─────────────────────────────────────────── */
  VideoPlayer.prototype._showRipple = function (isRight, secs) {
    var old = this.shell.querySelector('.vp-ripple');
    if (old) old.remove();
    var r = document.createElement('div');
    r.className = 'vp-ripple';
    r.style[isRight ? 'right' : 'left'] = '14%';
    r.innerHTML = (isRight ? '+' : '−') + secs + '<br><span class="vp-ripple-label">сек</span>';
    this.shell.appendChild(r);
    setTimeout(function () { if (r.parentNode) r.remove(); }, 700);
  };

  /* ── Watermark ───────────────────────────────────────────── */
  VideoPlayer.prototype._moveWatermark = function () {
    if (!this.watermark) return;
    var s = this.shell;
    var w = this.watermark;
    var maxX = Math.max(10, s.clientWidth  - w.clientWidth  - 10);
    var maxY = Math.max(10, s.clientHeight - w.clientHeight - 10);
    w.style.transform = 'translate(' +
      Math.floor(Math.random() * maxX) + 'px, ' +
      Math.floor(Math.random() * maxY) + 'px)';
  };
  VideoPlayer.prototype._initWatermark = function () {
    this._moveWatermark();
  };

  /* ── Layout recalc (orientation) ────────────────────────── */
  VideoPlayer.prototype._recalcLayout = function () {
    // Принудительный reflow чтобы браузер пересчитал размеры
    if (this.isPseudoFS) {
      this.shell.style.height = '';
      void this.shell.offsetHeight;
    }
    this._moveWatermark();
  };

  /* ══════════════════════════════════════════════════════════
     Fullscreen Manager
     Порядок попыток:
      1. iOS: video.webkitEnterFullscreen() — нативный плеер iOS
      2. Standard: shell.requestFullscreen()
      3. Pseudo-fullscreen (position: fixed)
     ══════════════════════════════════════════════════════════ */
  VideoPlayer.prototype.toggleFullscreen = function () {
    // Выход
    if (this.isPseudoFS) { this._exitPseudoFS(); return; }
    if (document.fullscreenElement || document.webkitFullscreenElement) {
      this._exitNativeFS(); return;
    }
    // Вход
    this._enterFullscreen();
  };

  VideoPlayer.prototype._enterFullscreen = function () {
    var self = this;
    var v    = this.video;
    var s    = this.shell;

    // Приоритет 1: iOS native fullscreen (лучшая поддержка на iPhone)
    // webkitEnterFullscreen работает напрямую с <video>, не с контейнером
    if (isIOS && v.webkitEnterFullscreen) {
      // Убеждаемся что видео готово
      if (v.readyState < 1) {
        v.load();
        v.addEventListener('loadedmetadata', function onMeta() {
          v.removeEventListener('loadedmetadata', onMeta);
          v.webkitEnterFullscreen();
        });
      } else {
        v.webkitEnterFullscreen();
      }
      return;
    }

    // Приоритет 2: Standard Fullscreen API на shell
    var req = s.requestFullscreen || s.webkitRequestFullscreen || s.mozRequestFullScreen;
    if (req) {
      var p = req.call(s);
      if (p && p.then) {
        p.then(function () {
          self._syncFSState();
          self._lockLandscape();
        }).catch(function () {
          self._enterPseudoFS();
        });
      } else {
        setTimeout(function () {
          if (document.fullscreenElement || document.webkitFullscreenElement) {
            self._syncFSState();
            self._lockLandscape();
          } else {
            self._enterPseudoFS();
          }
        }, 80);
      }
      return;
    }

    // Приоритет 3: Pseudo-fullscreen fallback
    this._enterPseudoFS();
  };

  VideoPlayer.prototype._exitNativeFS = function () {
    var exit = document.exitFullscreen || document.webkitExitFullscreen || document.mozCancelFullScreen;
    if (exit) exit.call(document);
  };

  VideoPlayer.prototype._enterPseudoFS = function () {
    this.isPseudoFS = true;
    this.shell.classList.add('vp-pseudo-fs');
    document.body.classList.add('vp-body-fs');
    this._syncFSState();
    this._lockLandscape();
  };

  VideoPlayer.prototype._exitPseudoFS = function () {
    this.isPseudoFS = false;
    this.shell.classList.remove('vp-pseudo-fs');
    document.body.classList.remove('vp-body-fs');
    this._syncFSState();
    this._unlockOrientation();
  };

  VideoPlayer.prototype._syncFSState = function () {
    var inNativeFS  = !!(document.fullscreenElement || document.webkitFullscreenElement);
    var inWebkitFS  = !!(this.video.webkitDisplayingFullscreen);
    var isFS = inNativeFS || inWebkitFS || this.isPseudoFS;
    this.fsBtn && (this.fsBtn.textContent = isFS ? '✕' : '⛶');
    if (!isFS) {
      this._unlockOrientation();
      // После выхода из нативного FS iOS — восстановить состояние
      this.isPseudoFS = false;
      this.shell.classList.remove('vp-pseudo-fs');
      document.body.classList.remove('vp-body-fs');
    }
  };

  VideoPlayer.prototype._lockLandscape = function () {
    try {
      if (screen.orientation && screen.orientation.lock) {
        screen.orientation.lock('landscape').catch(function () {});
      }
    } catch (e) {}
  };

  VideoPlayer.prototype._unlockOrientation = function () {
    try {
      if (screen.orientation && screen.orientation.unlock) {
        screen.orientation.unlock();
      }
    } catch (e) {}
  };

  /* ── Инициализация ───────────────────────────────────────── */
  function init() {
    var shell = document.getElementById('html5-video-shell');
    if (!shell) return; // Нет HTML5 плеера на этой странице
    window._vpInstance = new VideoPlayer(shell);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
