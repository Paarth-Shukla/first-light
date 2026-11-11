// Hash router. Routes look like "#/s/world" or "#/search?q=nvidia"; a view is async (el, params, ctx) => cleanup.
//
// Each render gets its own stage element and its own ctx. When the reader moves on before a slow view has
// finished, that view's stage is already out of the page and its ctx is dead, so whatever it does next
// (appending, setting the masthead, binding keys) cannot touch the page that replaced it.

const routes = [];
let current = { cleanup: null, token: 0 };
let outlet = null;
let hooks = {};

/** Register "/s/:section" style paths. "*" is the catch-all. */
export function route(path, view) {
  const names = [];
  const pattern = path === '*' ? null : new RegExp(`^${path.replace(/:[a-zA-Z]+/g, (name) => { names.push(name.slice(1)); return '([^/]+)'; })}/?$`);
  routes.push({ pattern, names, view, path });
}

/** "#/s/world?x=1" → {path: "/s/world", query: {x: "1"}}. Anything that is not an app route reads as "/". */
export function parseHash(hash = location.hash) {
  const text = hash.startsWith('#/') ? hash.slice(1) : '/';
  const [path, queryText = ''] = text.split('?');
  return { path, query: Object.fromEntries(new URLSearchParams(queryText)) };
}

export function buildHash(path, query = {}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '' && value !== false) params.set(key, String(value));
  }
  const text = params.toString();
  return `#${path}${text ? `?${text}` : ''}`;
}

export function go(path, query) {
  location.hash = buildHash(path, query);
}

/** Change the query of the current route without adding a history entry or re-rendering. */
export function replaceQuery(query) {
  const { path } = parseHash();
  history.replaceState(null, '', buildHash(path, query));
}

function decode(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value; // a truncated percent-escape in a pasted link: use it as written
  }
}

function match(path) {
  for (const entry of routes) {
    const found = entry.pattern?.exec(path);
    if (found) {
      const params = {};
      entry.names.forEach((name, index) => { params[name] = decode(found[index + 1]); });
      return { entry, params };
    }
  }
  return { entry: routes.find((r) => r.path === '*'), params: {} };
}

async function render() {
  const { path, query } = parseHash();
  const { entry, params: matched } = match(path);
  const token = ++current.token;
  if (typeof current.cleanup === 'function') {
    try { current.cleanup(); } catch (error) { console.error(error); }
  }
  current.cleanup = null;
  const alive = () => token === current.token;
  const stage = document.createElement('div');
  stage.className = 'stage';
  outlet.replaceChildren(stage);
  outlet.setAttribute('aria-busy', 'true');
  const ctx = { alive, shown: false, ...(hooks.context ? hooks.context(alive) : {}) };
  let cleanup = null;
  try {
    cleanup = await entry.view(stage, { ...matched, query, path }, ctx);
    ctx.shown = alive();
  } catch (error) {
    if (alive()) {
      console.error(error);
      hooks.error?.(stage, error, ctx);
    }
  }
  if (!alive()) { // abandoned: release whatever the view set up, and leave the page alone
    if (typeof cleanup === 'function') { try { cleanup(); } catch (error) { console.error(error); } }
    return;
  }
  current.cleanup = cleanup;
  outlet.removeAttribute('aria-busy');
  hooks.after?.();
}

/** options: context(alive) → extra ctx members; error(el, error, ctx); after(). */
export function start(element, options = {}) {
  outlet = element;
  hooks = options;
  window.addEventListener('hashchange', () => {
    // "#view" (the skip link) and other in-page anchors are not routes: move focus, keep the page
    if (location.hash && !location.hash.startsWith('#/')) { outlet.focus(); return; }
    render();
    window.scrollTo(0, 0);
  });
  return render();
}
