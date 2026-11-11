/* First Light — the few lines of behaviour the paper needs. No framework, no requests. */
(function () {
  var root = document.documentElement;

  function edition() {
    return root.getAttribute('data-theme') ||
      (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  }
  function setEdition(next) {
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('fl-theme', next); } catch (e) {}
    readTokens();
  }
  /* Specimen sheet: print each swatch's current value under it. */
  function readTokens() {
    var cs = getComputedStyle(root);
    document.querySelectorAll('[data-token]').forEach(function (el) {
      el.textContent = cs.getPropertyValue(el.getAttribute('data-token')).trim();
    });
  }
  readTokens();

  document.addEventListener('click', function (ev) {
    var t = ev.target.closest('[data-theme-toggle], [data-copy], [data-clip]');
    if (!t) return;
    if (t.hasAttribute('data-theme-toggle')) {
      setEdition(edition() === 'dark' ? 'light' : 'dark');
    } else if (t.hasAttribute('data-copy')) {
      var pre = t.closest('.prompt').querySelector('pre');
      var done = function () {
        t.textContent = 'Copied'; t.setAttribute('data-done', '');
        setTimeout(function () { t.textContent = 'Copy'; t.removeAttribute('data-done'); }, 1600);
      };
      if (navigator.clipboard) navigator.clipboard.writeText(pre.textContent).then(done, done); else done();
    } else {
      var on = t.getAttribute('aria-pressed') !== 'true';
      t.setAttribute('aria-pressed', String(on));
      t.textContent = on ? 'Clipped' : 'Clip';
    }
  });

  /* Keys: / focuses search, n switches edition. */
  document.addEventListener('keydown', function (ev) {
    if (ev.metaKey || ev.ctrlKey || ev.altKey || /^(INPUT|TEXTAREA|SELECT)$/.test(ev.target.tagName)) return;
    if (ev.key === '/') {
      var s = document.querySelector('[data-search]');
      if (s && s.offsetParent) { ev.preventDefault(); s.focus(); }
    } else if (ev.key === 'n') {
      setEdition(edition() === 'dark' ? 'light' : 'dark');
    }
  });

  /* Adoption ballot remembers its answer. */
  document.querySelectorAll('[data-adopt]').forEach(function (set) {
    var key = 'fl-' + set.querySelector('input').name;
    try {
      var saved = localStorage.getItem(key);
      if (saved) set.querySelectorAll('input').forEach(function (i) { i.checked = i.value === saved; });
    } catch (e) {}
    set.addEventListener('change', function (ev) {
      try { localStorage.setItem(key, ev.target.value); } catch (e) {}
    });
  });

  /* The column-inch gauge: the ruler scrolls under a fixed pointer; read off the inches. */
  var sheet = document.querySelector('.edition');
  var out = document.querySelector('[data-inch]');
  var gauge = document.querySelector('.gauge');
  var ofEl = document.querySelector('[data-inch-total]');
  if (sheet) {
    var measure = function () {
      var box = sheet.getBoundingClientRect();
      var line = gauge && getComputedStyle(gauge).display !== 'none' ? gauge.getBoundingClientRect().top + 4 : 0;
      var total = box.height / 96;
      var at = Math.max(0, Math.min(total, (line - box.top) / 96));
      if (out) out.textContent = Math.floor(at);
      if (ofEl) ofEl.textContent = 'of ' + Math.round(total);
      var span = box.height - window.innerHeight;
      root.style.setProperty('--read', span > 0 ? Math.max(0, Math.min(1, -box.top / span)).toFixed(3) : '0');
    };
    window.addEventListener('scroll', measure, { passive: true });
    window.addEventListener('resize', measure);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(measure);
    measure();
  }
})();
