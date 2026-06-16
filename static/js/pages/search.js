(function(){
  const qInput   = document.getElementById('search-q');
  const catSel   = document.getElementById('search-category');
  const lvlSel   = document.getElementById('search-level');
  const sortSel  = document.getElementById('search-sort');
  const results  = document.getElementById('search-results');
  const emptyEl  = document.getElementById('search-empty');
  const infoEl   = document.getElementById('search-info');
  const pagEl    = document.getElementById('search-pagination');
  let debounceTimer;
  let currentPage = 1;

  function clearNode(node) {
    if (node) node.replaceChildren();
  }

  function setInlineStyle(node, cssText) {
    node.style.cssText = cssText;
    return node;
  }

  function createTextElement(tag, text, className, cssText) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (cssText) node.style.cssText = cssText;
    node.textContent = text || '';
    return node;
  }

  function createSafeImage(src, alt, className, cssText) {
    const img = document.createElement('img');
    img.setAttribute('src', src || '');
    img.setAttribute('alt', alt || '');
    if (className) img.className = className;
    if (cssText) img.style.cssText = cssText;
    return img;
  }

  function createCourseCover(course) {
    const cover = document.createElement('div');
    cover.className = 'course-cover';

    if (course.image) {
      const img = createSafeImage(
        course.image,
        `${t('course.cover_alt') || 'Обложка курса'} ${course.title || ''}`,
        'course-cover-image'
      );
      img.setAttribute('loading', 'lazy');
      cover.appendChild(img);
      return cover;
    }

    const placeholder = document.createElement('div');
    placeholder.className = 'course-cover-placeholder';
    const letter = document.createElement('span');
    letter.className = 'course-cover-letter';
    letter.textContent = (course.title || '?').trim().charAt(0).toUpperCase() || '?';
    placeholder.appendChild(letter);
    cover.appendChild(placeholder);
    return cover;
  }

  function doSearch(page) {
    currentPage = page || 1;
    const params = new URLSearchParams({
      q: qInput.value,
      category_id: catSel.value || 0,
      level: lvlSel.value,
      sort: sortSel.value,
      page: currentPage,
      per_page: 12
    });

    fetch('/api/search?' + params)
      .then(r => r.json())
      .then(data => {
        clearNode(results);
        emptyEl.style.display = 'none';

        // ── Организации ──────────────────────────────────────────────────────
        const orgsContainer = document.getElementById('search-organizations');
        clearNode(orgsContainer);
        if (data.organizations && data.organizations.length > 0) {
          const h = document.createElement('h2');
          h.setAttribute('data-i18n', 'search.orgs_title');
          h.textContent = t('search.orgs_title') || 'Учебные центры';
          h.style.cssText = 'font-size:1.1rem;font-weight:600;margin-bottom:14px;width:100%;grid-column:1/-1;';
          orgsContainer.appendChild(h);

          data.organizations.forEach(o => {
            const card = document.createElement('div');
            card.className = 'course-card';
            card.style.cssText = 'display:flex;flex-direction:column;';

            const body = setInlineStyle(document.createElement('div'), 'text-align:center;flex:1;');
            body.className = 'course-card-body';

            const logoWrap = setInlineStyle(document.createElement('div'), 'margin:0 auto 12px;width:56px;height:56px;');
            if (o.logo_url) {
              logoWrap.appendChild(createSafeImage(
                o.logo_url,
                o.name || '',
                '',
                'width:56px;height:56px;border-radius:12px;object-fit:cover;'
              ));
            } else {
              const fallback = setInlineStyle(document.createElement('div'), 'width:56px;height:56px;border-radius:12px;background:var(--surface-soft,#f0f2f5);display:flex;align-items:center;justify-content:center;font-size:1.6rem;');
              fallback.textContent = '🏢';
              logoWrap.appendChild(fallback);
            }
            body.appendChild(logoWrap);
            body.appendChild(createTextElement('h3', o.name, 'course-title', 'font-size:1rem;margin-bottom:6px;'));
            body.appendChild(createTextElement('p', o.description, 'course-desc', 'font-size:.85rem;'));

            const footer = setInlineStyle(document.createElement('div'), 'display:flex;flex-direction:column;gap:8px;padding:14px 16px;');
            footer.className = 'course-card-footer';
            const openLink = setInlineStyle(document.createElement('a'), 'width:100%;text-align:center;');
            openLink.className = 'btn btn-outline';
            openLink.setAttribute('href', `/organization/${encodeURIComponent(o.id)}`);
            openLink.textContent = t('org.open_btn') || 'Открыть';
            footer.appendChild(openLink);

            card.appendChild(body);
            card.appendChild(footer);
            orgsContainer.appendChild(card);
          });

          if (typeof translatePage === 'function') translatePage();
        }

        // ── Преподаватели ────────────────────────────────────────
        const teachersSection = document.getElementById('search-teachers-section');
        const teachersContainer = document.getElementById('search-teachers');
        clearNode(teachersContainer);
        if (data.teachers && data.teachers.length > 0) {
          teachersSection.style.display = 'block';
          data.teachers.forEach(teacher => {
            const card = document.createElement('a');
            card.setAttribute('href', `/teachers/${encodeURIComponent(teacher.id)}`);
            card.style.cssText = 'display:flex;align-items:center;gap:12px;background:var(--bg-card,white);border:1px solid rgba(0,0,0,0.08);border-radius:12px;padding:14px 18px;text-decoration:none;color:inherit;transition:box-shadow .2s;min-width:200px;flex:1;max-width:320px;';
            card.onmouseenter = () => card.style.boxShadow = '0 4px 16px rgba(0,0,0,0.1)';
            card.onmouseleave = () => card.style.boxShadow = '';

            if (teacher.avatar) {
              card.appendChild(createSafeImage(
                teacher.avatar,
                teacher.name || '',
                '',
                'width:44px;height:44px;border-radius:50%;object-fit:cover;'
              ));
            } else {
              const avatar = setInlineStyle(document.createElement('div'), 'width:44px;height:44px;border-radius:50%;background:linear-gradient(135deg,#6366f1,#8b5cf6);display:flex;align-items:center;justify-content:center;color:white;font-weight:700;font-size:1.1rem;flex-shrink:0;');
              avatar.textContent = (teacher.name || '?').charAt(0).toUpperCase() || '?';
              card.appendChild(avatar);
            }

            const info = document.createElement('div');
            const nameLine = setInlineStyle(document.createElement('div'), 'font-weight:600;font-size:0.95rem;');
            nameLine.textContent = `👨‍🏫 ${teacher.name || ''}${teacher.org_name ? ' · ' + teacher.org_name : ''}`;
            info.appendChild(nameLine);
            if (teacher.bio) {
              info.appendChild(createTextElement('div', teacher.bio, '', 'font-size:0.82rem;color:var(--text-muted);margin-top:2px;'));
            }
            card.appendChild(info);
            teachersContainer.appendChild(card);
          });
        } else {
          teachersSection.style.display = 'none';
        }

        // ── Курсы ────────────────────────────────────────────────
        const titleEl = document.querySelector('h1[data-i18n="search.title"]');
        if (!qInput.value) {
            if (titleEl) {
                titleEl.setAttribute('data-i18n', 'search.popular_title');
                titleEl.textContent = t('search.popular_title') || 'Популярные курсы и учебные центры';
                if (typeof translatePage === 'function') translatePage();
            }
        } else {
            if (titleEl) {
                titleEl.setAttribute('data-i18n', 'search.title');
                titleEl.textContent = '🔍 Поиск';
                if (typeof translatePage === 'function') translatePage();
            }
        }

        if (data.courses.length === 0 && (!data.organizations || data.organizations.length === 0) && (!data.teachers || data.teachers.length === 0)) {
          emptyEl.style.display = 'block';
          infoEl.textContent = '';
          clearNode(pagEl);
          return;
        }

        if (data.courses.length > 0) {
          infoEl.textContent = t('search.found', { count: data.total });
        }

        data.courses.forEach((c, i) => {
          const card = document.createElement('div');
          card.className = 'course-card';
          card.style.animation = 'fadeInUp .4s ' + (i * 0.05) + 's ease both';
          const rating = Number(c.rating) || 0;
          const roundedRating = Math.max(0, Math.min(5, Math.round(rating)));
          const stars = '★'.repeat(roundedRating) + '☆'.repeat(5 - roundedRating);

          const header = document.createElement('div');
          header.className = 'course-card-header';
          header.appendChild(createCourseCover(c));
          if (c.category) {
            header.appendChild(createTextElement('span', c.category, 'category-badge'));
          }

          const body = document.createElement('div');
          body.className = 'course-card-body';
          body.appendChild(createTextElement('h3', c.title, 'course-title'));
          body.appendChild(createTextElement('p', c.description || t('common.no_desc'), 'course-desc'));

          const meta = document.createElement('div');
          meta.className = 'course-meta';
          const teacher = setInlineStyle(document.createElement('span'), 'display:flex;align-items:center;gap:5px;flex-wrap:wrap;');
          teacher.className = 'course-teacher';
          teacher.appendChild(document.createTextNode(`👨‍🏫 ${c.teacher_name || ''}`));
          if (Array.isArray(c.teacher_orgs)) {
            c.teacher_orgs.forEach(orgTeacher => {
              teacher.appendChild(document.createTextNode(' · '));
              teacher.appendChild(document.createTextNode(orgTeacher.name || ''));
            });
          }
          meta.appendChild(teacher);
          meta.appendChild(createTextElement('span', `${stars} ${rating.toFixed(1)}`, 'rating-text', 'font-size:.85rem;'));
          body.appendChild(meta);

          const badges = setInlineStyle(document.createElement('div'), 'display:flex;gap:8px;margin-top:4px;');
          if (c.level) {
            badges.appendChild(createTextElement('span', t('level.' + c.level.toLowerCase()), 'level-badge'));
          }
          body.appendChild(badges);

          const footer = document.createElement('div');
          footer.className = 'course-card-footer';
          const moreLink = document.createElement('a');
          moreLink.className = 'btn btn-primary btn-sm';
          moreLink.setAttribute('href', `/courses/${encodeURIComponent(c.id)}`);
          moreLink.textContent = `${t('common.more')} →`;
          footer.appendChild(moreLink);

          card.appendChild(header);
          card.appendChild(body);
          card.appendChild(footer);
          results.appendChild(card);
        });

        // Пагинация
        const totalPages = Math.ceil(data.total / data.per_page);
        clearNode(pagEl);
        for (let p = 1; p <= totalPages; p++) {
          const btn = document.createElement('button');
          btn.textContent = p;
          btn.className = 'btn ' + (p === currentPage ? 'btn-primary' : 'btn-secondary') + ' btn-sm';
          btn.onclick = () => doSearch(p);
          pagEl.appendChild(btn);
        }
      });
  }

  // Debounce при вводе
  qInput.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => doSearch(1), 400);
  });
  catSel.addEventListener('change', () => doSearch(1));
  lvlSel.addEventListener('change', () => doSearch(1));
  sortSel.addEventListener('change', () => doSearch(1));
  window.refreshSearchResults = doSearch;

  // Начальный поиск (чтение 'q' из URL если есть)
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.has('q')) {
    qInput.value = urlParams.get('q');
  }

  doSearch(1);
})();

async function studentJoinOrg(orgId, hasOtherOrg) {
    if (hasOtherOrg) {
        const confirmSwitchText = t('org.confirm_switch_btn');
        const confirmed = await showConfirmModal(
            t('org.confirm_switch') || 'Смена учебного центра',
            t('org.confirm_switch_hint') || 'Вы состоите в другом учебном центре. При смене вы будете отчислены из текущего и зачислены в новый.',
            confirmSwitchText === 'org.confirm_switch_btn' ? 'Да, сменить' : confirmSwitchText,
            t('action.cancel') || 'Отмена',
            true
        );
        if (!confirmed) return;
    }

    try {
        const url = `/organization/${orgId}/student/join${hasOtherOrg ? '?force=true' : ''}`;
        const r = await fetch(url, { method: 'POST' });
        let data = {};
        try { data = await r.json(); } catch (_) {}

        if (r.ok) {
            showToast(data.auto_accepted ? t('org.join_success') : t('org.join_sent'), 'success');
            if (typeof window.refreshSearchResults === 'function') window.refreshSearchResults();
        } else {
            showToast(data.detail || t('common.error_conn') || 'Произошла ошибка.', 'error');
        }
    } catch (e) {
        console.error(e);
        showToast(t('common.error_conn') || 'Нет связи с сервером.', 'error');
    }
}
