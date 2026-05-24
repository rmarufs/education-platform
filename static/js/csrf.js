(function () {
  const meta = document.querySelector('meta[name="csrf-token"]');
  const token = meta ? meta.getAttribute('content') : '';
  if (!token) return;

  function isUnsafeMethod(method) {
    return !['GET', 'HEAD', 'OPTIONS'].includes(String(method || 'GET').toUpperCase());
  }

  function ensureFormToken(form) {
    if (!form || !isUnsafeMethod(form.method)) return;
    let input = form.querySelector('input[name="csrf_token"]');
    if (!input) {
      input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'csrf_token';
      form.appendChild(input);
    }
    input.value = token;
  }

  function ensureAllForms(root) {
    (root || document).querySelectorAll('form').forEach(ensureFormToken);
  }

  ensureAllForms(document);

  document.addEventListener('submit', function (event) {
    ensureFormToken(event.target);
  }, true);

  const nativeSubmit = HTMLFormElement.prototype.submit;
  HTMLFormElement.prototype.submit = function () {
    ensureFormToken(this);
    return nativeSubmit.call(this);
  };

  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      mutation.addedNodes.forEach((node) => {
        if (node.nodeType !== Node.ELEMENT_NODE) return;
        if (node.matches && node.matches('form')) ensureFormToken(node);
        if (node.querySelectorAll) ensureAllForms(node);
      });
    });
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });

  if (window.fetch) {
    const nativeFetch = window.fetch.bind(window);
    window.fetch = function (resource, options) {
      const opts = options ? { ...options } : {};
      const method = opts.method || (resource && resource.method) || 'GET';
      if (isUnsafeMethod(method)) {
        const headers = new Headers(opts.headers || {});
        headers.set('X-CSRF-Token', token);
        opts.headers = headers;
      }
      return nativeFetch(resource, opts);
    };
  }
})();
