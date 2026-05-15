(function () {
  'use strict';

  var ytApiPromise = null;
  var isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;

  function decodeToken(token) {
    if (!token) return '';
    try {
      var binary = atob(token);
      var decoded;
      if (window.TextDecoder) {
        var bytes = new Uint8Array(binary.length);
        for (var i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
        decoded = new TextDecoder('utf-8').decode(bytes);
      } else {
        decoded = decodeURIComponent(escape(binary));
      }
      var original = '';
      for (var j = 0; j < decoded.length; j += 1) {
        original += String.fromCharCode(decoded.charCodeAt(j) - 3);
      }
      return original.split('').reverse().join('');
    } catch (_) {
      return '';
    }
  }

  function fmt(seconds) {
    seconds = Number(seconds);
    if (!isFinite(seconds) || seconds < 0) seconds = 0;
    seconds = Math.round(seconds);
    var h = Math.floor(seconds / 3600);
    var m = Math.floor((seconds % 3600) / 60);
    var s = seconds % 60;
    if (h > 0) return h + ':' + (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
    return m + ':' + (s < 10 ? '0' : '') + s;
  }

  function loadYouTubeApi() {
    if (window.YT && window.YT.Player) return Promise.resolve(window.YT);
    if (ytApiPromise) return ytApiPromise;

    ytApiPromise = new Promise(function (resolve) {
      var previous = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = function () {
        if (typeof previous === 'function') previous();
        resolve(window.YT);
      };
      var script = document.createElement('script');
      script.src = 'https://www.youtube.com/iframe_api';
      script.async = true;
      document.head.appendChild(script);
    });

    return ytApiPromise;
  }

  function ProtectedVideoPlayer(shell) {
    this.shell = shell;
    this.provider = shell.getAttribute('data-vp-provider');
    this.token = shell.getAttribute('data-video-token') || '';
    this.video = shell.querySelector('.vp-video');
    this.youtubeMount = shell.querySelector('.vp-youtube');
    this.clickLayer = shell.querySelector('.vp-click-layer');
    this.playBtn = shell.querySelector('.vp-play');
    this.muteBtn = shell.querySelector('.vp-mute');
    this.fsBtn = shell.querySelector('.vp-fullscreen');
    this.progress = shell.querySelector('.vp-progress');
    this.fill = shell.querySelector('.vp-progress-fill');
    this.handle = shell.querySelector('.vp-progress-handle');
    this.time = shell.querySelector('.vp-time');
    this.bigPlay = shell.querySelector('.vp-big-play');

    this.player = null;
    this.ready = false;
    this.playing = false;
    this.muted = false;
    this.seeking = false;
    this.seekPercent = 0;
    this.wasPlayingBeforeSeek = false;

    this.bindCommon();
    if (this.provider === 'youtube') this.initYouTube();
    else this.initHtml5();
  }

  ProtectedVideoPlayer.prototype.bindCommon = function () {
    var self = this;

    this.shell.addEventListener('contextmenu', function (event) {
      event.preventDefault();
    });

    if (this.playBtn) {
      this.playBtn.addEventListener('click', function (event) {
        event.preventDefault();
        self.togglePlay();
      });
    }

    if (this.clickLayer) {
      this.clickLayer.addEventListener('click', function (event) {
        event.preventDefault();
        self.togglePlay();
      });
    }

    if (this.muteBtn) {
      this.muteBtn.addEventListener('click', function (event) {
        event.preventDefault();
        self.toggleMute();
      });
    }

    if (this.fsBtn) {
      if (isIOS || !this.shell.requestFullscreen) {
        this.fsBtn.hidden = true;
      } else {
        this.fsBtn.addEventListener('click', function (event) {
          event.preventDefault();
          self.toggleFullscreen();
        });
      }
    }

    this.bindSeek();

    if (this.progress) {
      this.progress.addEventListener('keydown', function (event) {
        self.handleSeekKey(event);
      });
    }

    document.addEventListener('fullscreenchange', function () {
      self.syncFullscreen();
    });

    this.progressTimer = window.setInterval(function () {
      self.refreshProgress();
    }, 250);
  };

  ProtectedVideoPlayer.prototype.initHtml5 = function () {
    var self = this;
    var src = decodeToken(this.token);
    if (!this.video || !src) {
      this.showError();
      return;
    }

    this.video.src = src;
    this.video.load();

    this.video.addEventListener('loadedmetadata', function () {
      self.ready = true;
      self.refreshProgress();
    });
    this.video.addEventListener('play', function () {
      self.setPlaying(true);
    });
    this.video.addEventListener('pause', function () {
      self.setPlaying(false);
    });
    this.video.addEventListener('ended', function () {
      self.setPlaying(false);
      self.refreshProgress();
    });
    this.video.addEventListener('timeupdate', function () {
      self.refreshProgress();
    });
    this.video.addEventListener('waiting', function () {
      self.shell.classList.add('vp-loading');
    });
    this.video.addEventListener('canplay', function () {
      self.shell.classList.remove('vp-loading');
    });
    this.video.addEventListener('error', function () {
      self.showError();
    });
  };

  ProtectedVideoPlayer.prototype.initYouTube = function () {
    var self = this;
    var videoId = decodeToken(this.token);
    if (!this.youtubeMount || !videoId) {
      this.showError();
      return;
    }

    loadYouTubeApi().then(function (YT) {
      self.player = new YT.Player(self.youtubeMount, {
        videoId: videoId,
        host: 'https://www.youtube-nocookie.com',
        playerVars: {
          autoplay: 0,
          controls: 0,
          rel: 0,
          modestbranding: 1,
          disablekb: 1,
          fs: 0,
          playsinline: 1,
          iv_load_policy: 3,
          cc_load_policy: 0,
          origin: window.location.origin,
          widget_referrer: window.location.origin
        },
        events: {
          onReady: function () {
            self.ready = true;
            self.prepareYouTubeIframe();
            self.refreshProgress();
          },
          onStateChange: function (event) {
            self.onYouTubeStateChange(event);
          },
          onError: function () {
            self.showError();
          }
        }
      });
    });
  };

  ProtectedVideoPlayer.prototype.prepareYouTubeIframe = function () {
    if (!this.player || !this.player.getIframe) return;
    var iframe = this.player.getIframe();
    if (!iframe) return;
    iframe.setAttribute('referrerpolicy', 'no-referrer');
    iframe.setAttribute('allow', 'autoplay; encrypted-media; picture-in-picture');
    iframe.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-presentation');
    iframe.setAttribute('tabindex', '-1');
  };

  ProtectedVideoPlayer.prototype.onYouTubeStateChange = function (event) {
    if (!window.YT || !window.YT.PlayerState) return;
    if (event.data === window.YT.PlayerState.PLAYING) {
      this.setPlaying(true);
    } else if (event.data === window.YT.PlayerState.PAUSED || event.data === window.YT.PlayerState.CUED) {
      this.setPlaying(false);
    } else if (event.data === window.YT.PlayerState.ENDED) {
      this.setPlaying(false);
      try {
        this.player.seekTo(0, false);
      } catch (_) {}
      this.setProgressVisual(0, 0, this.getDuration());
    }
  };

  ProtectedVideoPlayer.prototype.showError = function () {
    this.shell.classList.add('vp-error-state');
  };

  ProtectedVideoPlayer.prototype.setPlaying = function (playing) {
    this.playing = !!playing;
    this.shell.classList.toggle('vp-playing', this.playing);
    if (this.playBtn) this.playBtn.textContent = this.playing ? '\u23f8' : '\u25b6';
    if (this.bigPlay) this.bigPlay.textContent = this.playing ? '' : '\u25b6';
  };

  ProtectedVideoPlayer.prototype.isPlaying = function () {
    if (this.provider === 'html5') {
      return !!(this.video && !this.video.paused && !this.video.ended);
    }
    return this.playing;
  };

  ProtectedVideoPlayer.prototype.play = function () {
    if (!this.ready && this.provider === 'youtube') return;
    if (this.provider === 'html5') {
      if (!this.video) return;
      var promise = this.video.play();
      if (promise && promise.catch) promise.catch(function () {});
    } else if (this.player && this.player.playVideo) {
      this.player.playVideo();
    }
  };

  ProtectedVideoPlayer.prototype.pause = function () {
    if (this.provider === 'html5') {
      if (this.video) this.video.pause();
    } else if (this.player && this.player.pauseVideo) {
      this.player.pauseVideo();
    }
  };

  ProtectedVideoPlayer.prototype.togglePlay = function () {
    if (this.isPlaying()) this.pause();
    else this.play();
  };

  ProtectedVideoPlayer.prototype.toggleMute = function () {
    this.muted = !this.muted;
    if (this.provider === 'html5') {
      if (this.video) this.video.muted = this.muted;
    } else if (this.player) {
      if (this.muted && this.player.mute) this.player.mute();
      if (!this.muted && this.player.unMute) this.player.unMute();
    }
    if (this.muteBtn) this.muteBtn.textContent = this.muted ? '\ud83d\udd07' : '\ud83d\udd0a';
  };

  ProtectedVideoPlayer.prototype.getCurrentTime = function () {
    if (this.provider === 'html5') return this.video ? (this.video.currentTime || 0) : 0;
    if (this.player && this.player.getCurrentTime) return this.player.getCurrentTime() || 0;
    return 0;
  };

  ProtectedVideoPlayer.prototype.getDuration = function () {
    if (this.provider === 'html5') return this.video ? (this.video.duration || 0) : 0;
    if (this.player && this.player.getDuration) return this.player.getDuration() || 0;
    return 0;
  };

  ProtectedVideoPlayer.prototype.seekTo = function (seconds) {
    var duration = this.getDuration();
    if (!duration) return;
    seconds = Math.max(0, Math.min(duration, seconds));
    if (this.provider === 'html5') {
      if (this.video) this.video.currentTime = seconds;
    } else if (this.player && this.player.seekTo) {
      this.player.seekTo(seconds, true);
    }
    this.setProgressVisual((seconds / duration) * 100, seconds, duration);
  };

  ProtectedVideoPlayer.prototype.refreshProgress = function () {
    if (this.seeking) return;
    var duration = this.getDuration();
    var current = this.getCurrentTime();
    var pct = duration > 0 ? (current / duration) * 100 : 0;
    this.setProgressVisual(pct, current, duration);
  };

  ProtectedVideoPlayer.prototype.setProgressVisual = function (pct, current, duration) {
    pct = Math.max(0, Math.min(100, pct || 0));
    if (this.fill) this.fill.style.width = pct + '%';
    if (this.handle) this.handle.style.left = pct + '%';
    if (this.progress) {
      this.progress.style.setProperty('--vp-progress', pct + '%');
      this.progress.setAttribute('aria-valuenow', String(Math.round(pct)));
    }
    if (this.time) this.time.textContent = fmt(current) + ' / ' + fmt(duration);
  };

  ProtectedVideoPlayer.prototype.bindSeek = function () {
    var self = this;
    if (!this.progress) return;

    function pointFromEvent(event) {
      if (event.touches && event.touches.length) return event.touches[0];
      if (event.changedTouches && event.changedTouches.length) return event.changedTouches[0];
      return event;
    }

    function percentFromEvent(event) {
      var point = pointFromEvent(event);
      var rect = self.progress.getBoundingClientRect();
      if (!rect.width) return 0;
      return Math.max(0, Math.min(1, (point.clientX - rect.left) / rect.width));
    }

    function preview(event) {
      var duration = self.getDuration();
      if (!duration) return;
      self.seekPercent = percentFromEvent(event);
      self.setProgressVisual(self.seekPercent * 100, self.seekPercent * duration, duration);
    }

    function start(event) {
      if (event.type === 'mousedown' && event.button !== 0) return;
      var duration = self.getDuration();
      if (!duration) return;
      event.preventDefault();
      event.stopPropagation();
      self.seeking = true;
      self.wasPlayingBeforeSeek = self.isPlaying();
      self.shell.classList.add('vp-seeking');
      if (self.wasPlayingBeforeSeek) self.pause();
      preview(event);
    }

    function move(event) {
      if (!self.seeking) return;
      event.preventDefault();
      preview(event);
    }

    function end(event) {
      if (!self.seeking) return;
      event.preventDefault();
      preview(event);
      var duration = self.getDuration();
      self.seekTo(self.seekPercent * duration);
      self.seeking = false;
      self.shell.classList.remove('vp-seeking');
      if (self.wasPlayingBeforeSeek) self.play();
    }

    if (window.PointerEvent) {
      this.progress.addEventListener('pointerdown', function (event) {
        start(event);
        if (!self.seeking) return;
        try {
          self.progress.setPointerCapture(event.pointerId);
        } catch (_) {}
      });
      this.progress.addEventListener('pointermove', move);
      this.progress.addEventListener('pointerup', end);
      this.progress.addEventListener('pointercancel', end);
    } else {
      this.progress.addEventListener('mousedown', function (event) {
        start(event);
        document.addEventListener('mousemove', move);
        document.addEventListener('mouseup', onMouseUp);
      });
      this.progress.addEventListener('touchstart', function (event) {
        start(event);
        document.addEventListener('touchmove', move, { passive: false });
        document.addEventListener('touchend', onTouchEnd);
        document.addEventListener('touchcancel', onTouchEnd);
      }, { passive: false });
    }

    function onMouseUp(event) {
      end(event);
      document.removeEventListener('mousemove', move);
      document.removeEventListener('mouseup', onMouseUp);
    }

    function onTouchEnd(event) {
      end(event);
      document.removeEventListener('touchmove', move);
      document.removeEventListener('touchend', onTouchEnd);
      document.removeEventListener('touchcancel', onTouchEnd);
    }
  };

  ProtectedVideoPlayer.prototype.handleSeekKey = function (event) {
    var duration = this.getDuration();
    if (!duration) return;
    var current = this.getCurrentTime();
    if (event.key === 'ArrowLeft') current -= 5;
    else if (event.key === 'ArrowRight') current += 5;
    else if (event.key === 'Home') current = 0;
    else if (event.key === 'End') current = duration;
    else return;
    event.preventDefault();
    this.seekTo(current);
  };

  ProtectedVideoPlayer.prototype.toggleFullscreen = function () {
    var self = this;
    if (document.fullscreenElement) {
      var exitPromise = document.exitFullscreen();
      if (exitPromise && exitPromise.catch) exitPromise.catch(function () {});
      return;
    }
    var requestPromise = this.shell.requestFullscreen();
    if (!requestPromise || !requestPromise.then) {
      this.syncFullscreen();
      return;
    }
    requestPromise.then(function () {
      self.syncFullscreen();
    }).catch(function () {});
  };

  ProtectedVideoPlayer.prototype.syncFullscreen = function () {
    var active = document.fullscreenElement === this.shell;
    this.shell.classList.toggle('vp-fullscreen-active', active);
    if (this.fsBtn) this.fsBtn.textContent = active ? '\u00d7' : '\u26f6';
  };

  function init() {
    document.querySelectorAll('.vp-shell[data-vp-provider]').forEach(function (shell) {
      if (!shell.__protectedVideoPlayer) {
        shell.__protectedVideoPlayer = new ProtectedVideoPlayer(shell);
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
