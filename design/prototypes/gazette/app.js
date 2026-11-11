/* First Light: the few lines of script the Gazette needs.
   Theme switch, copy button, phone index sheet, "/" for search, j/k on The Wire. */
(function () {
  var root = document.documentElement;

  function theme() {
    var set = root.getAttribute('data-theme');
    if (set) return set;
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  function toggleTheme() {
    var next = theme() === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('first-light-theme', next); } catch (e) {}
  }
  document.querySelectorAll('[data-theme-toggle]').forEach(function (b) {
    b.addEventListener('click', toggleTheme);
  });

  document.querySelectorAll('[data-copy]').forEach(function (b) {
    b.addEventListener('click', function () {
      var src = document.querySelector(b.getAttribute('data-copy'));
      var label = b.querySelector('[data-copy-label]');
      if (!src) return;
      var done = function () {
        b.setAttribute('data-done', 'true');
        label.textContent = 'Copied';
        setTimeout(function () { b.removeAttribute('data-done'); label.textContent = 'Copy'; }, 1800);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(src.textContent).then(done, done);
      } else { done(); }
    });
  });

  var sheet = document.getElementById('sheet');
  var opener = null;
  function setSheet(open) {
    if (!sheet) return;
    sheet.setAttribute('data-open', open ? 'true' : 'false');
    if (open) { var c = sheet.querySelector('[data-sheet-close]'); if (c) c.focus(); }
    else if (opener) { opener.focus(); }
  }
  document.querySelectorAll('[data-sheet-open]').forEach(function (b) {
    b.addEventListener('click', function (e) {
      if (!sheet || !window.matchMedia('(max-width: 64rem)').matches) return;
      e.preventDefault(); opener = b; setSheet(true);
    });
  });
  document.querySelectorAll('[data-sheet-close]').forEach(function (b) {
    b.addEventListener('click', function () { setSheet(false); });
  });

  document.querySelectorAll('button.chip[aria-pressed]').forEach(function (c) {
    c.addEventListener('click', function () {
      c.setAttribute('aria-pressed', c.getAttribute('aria-pressed') === 'true' ? 'false' : 'true');
    });
  });

  /* The finite edition: count the dispatches that have crossed the screen. */
  var dispatches = Array.prototype.slice.call(document.querySelectorAll('[id^="no-"]'));
  var meter = document.querySelector('[data-progress-n]');
  var folio = document.querySelector('.folio');
  var seen = {};
  function count() {
    var h = window.innerHeight, n = 0;
    dispatches.forEach(function (d) {
      if (!seen[d.id] && d.getBoundingClientRect().bottom <= h) seen[d.id] = true;
      if (seen[d.id]) n++;
    });
    if (meter) meter.textContent = n;
    if (folio) folio.style.setProperty('--progress', dispatches.length ? n / dispatches.length : 0);
    root.setAttribute('data-reading', window.scrollY > 240 ? 'true' : 'false');
  }
  if (dispatches.length && meter) {
    window.addEventListener('scroll', count, { passive: true });
    window.addEventListener('resize', count);
    count();
  }

  /* j and k walk the dispatches in numbered order. */
  var at = 0;
  function walk(step) {
    var total = dispatches.length;
    if (!total) return;
    at = Math.max(1, Math.min(total, at + step));
    var el = document.getElementById('no-' + at);
    var link = el && (el.querySelector('h3 a') || el.querySelector('a[href]:not(.story__desk)'));
    if (link) { link.focus({ preventScroll: true }); el.scrollIntoView({ block: 'center' }); }
  }

  var wire = document.querySelector('[data-wire]');
  function moveWire(step) {
    var rows = Array.prototype.slice.call(wire.querySelectorAll('.wire__row'));
    var at = rows.findIndex(function (r) { return r.getAttribute('aria-selected') === 'true'; });
    var to = Math.max(0, Math.min(rows.length - 1, at + step));
    rows.forEach(function (r, i) {
      r.setAttribute('aria-selected', i === to ? 'true' : 'false');
      r.tabIndex = i === to ? 0 : -1;
    });
    rows[to].focus({ preventScroll: false });
  }

  document.addEventListener('keydown', function (e) {
    var typing = /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName);
    if (e.key === 'Escape') { setSheet(false); if (typing) e.target.blur(); return; }
    if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === '/') {
      var q = document.querySelector('[data-search]');
      if (q) { e.preventDefault(); q.focus(); }
    } else if (e.key === 'n') {
      toggleTheme();
    } else if (wire && (e.key === 'j' || e.key === 'k')) {
      e.preventDefault(); moveWire(e.key === 'j' ? 1 : -1);
    } else if (e.key === 'j' || e.key === 'k') {
      e.preventDefault(); walk(e.key === 'j' ? 1 : -1);
    } else if (e.key === 'o' && document.activeElement && document.activeElement.tagName === 'A') {
      document.activeElement.click();
    } else if (wire && e.key === 'm') {
      var sel = wire.querySelector('[aria-selected="true"]');
      if (sel) sel.setAttribute('data-unread', sel.getAttribute('data-unread') === 'true' ? 'false' : 'true');
    }
  });
})();
