// The shell: masthead, navigation, phone tab bar and desk sheet, footer, theme, keys and the "go to" palette.
// Views call setPage()/setFrontPlate() to say what the masthead should carry.

import { h, arw, clear, $, $$ } from './core/dom.js';
import * as store from './core/store.js';
import * as data from './core/data.js';
import { allDesks, chg, fmtNumber, plural } from './core/ui.js';
import { clock, longDate, shortDate, fromDay, zoneName, hoursSince } from './core/time.js';
import { go } from './core/router.js';
import { warm } from './search/client.js';

const NAV = [
  { id: 'front', name: 'Front Page', href: '#/', key: 'F' },
  { id: 'wire', name: 'The Wire', href: '#/wire', key: 'W' },
  { id: 'markets', name: 'Markets', href: '#/markets', key: 'M' },
  { id: 'weekend', name: 'Weekend Review', href: '#/weekend', key: 'R' },
  { id: 'claude', name: 'Claude Desk', href: '#/claude', key: 'C' },
  { id: 'clippings', name: 'Clippings', href: '#/clippings', key: 'L' },
];

const state = { manifest: null, nav: 'front', wireNew: 0, page: null, seen: [0, 0] };

// ---- theme -------------------------------------------------------------------

const root = document.documentElement;
const currentTheme = () => root.getAttribute('data-theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');

export function setTheme(theme) { // 'dark' | 'light' | 'auto'
  if (theme === 'auto') root.removeAttribute('data-theme');
  else root.setAttribute('data-theme', theme);
  store.update('prefs', {}, (prefs) => ({ ...prefs, theme }));
  syncTheme();
}

export const toggleTheme = () => setTheme(currentTheme() === 'dark' ? 'light' : 'dark');

function syncTheme() {
  for (const button of $$('.theme-toggle')) button.setAttribute('aria-pressed', String(currentTheme() === 'dark'));
  const meta = $('meta[name="theme-color"]');
  if (meta) meta.content = currentTheme() === 'dark' ? '#0a0a0b' : '#0b0b0b';
}

// ---- toast ---------------------------------------------------------------------

let toastTimer = null;
export function toast(message) {
  const el = $('#toast');
  el.textContent = message;
  el.classList.add('is-on');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('is-on'), 2600);
}

// ---- masthead --------------------------------------------------------------------

function topbar() {
  const m = state.manifest;
  const stale = m && hoursSince(m.builtAt) > 26;
  const editionDay = m?.edition?.date;
  return h('div.topbar', h('div.wrap.topbar__in',
    h('p.topbar__date.label',
      h('b', editionDay ? h('time', { datetime: editionDay }, longDate(fromDay(editionDay))) : 'First Light'),
      h('span', 'Morning edition'),
      m && h(`span${stale ? '.is-stale' : ''}`, { title: 'When the data on this page was last built' },
        stale ? `Stale: last built ${shortDate(m.builtAt)} ${clock(m.builtAt)}` : `Updated ${clock(m.builtAt)} ${zoneName()}`),
      // the masthead is re-set on every clip and Wire count change: keep the last count
      h('span#seen', { hidden: !state.seen[1] }, state.seen[1] ? `${state.seen[0]} of ${state.seen[1]} seen` : '')),
    h('ul.topbar__links.label',
      h('li', h('a', { href: '#/archive' }, 'Back Issues')),
      h('li', h('a', { href: '#/settings' }, 'Settings')),
      h('li', h('a', { href: '#/colophon' }, 'Colophon'))),
    h('button.theme-toggle.label', { type: 'button', 'aria-pressed': 'false', onclick: toggleTheme },
      h('span.theme-toggle__lamp', { 'aria-hidden': 'true' }),
      h('span.when-light', 'Night edition'), h('span.when-dark', 'Day edition'))));
}

function nameplate(tag) {
  return h('div.nameplate',
    h('p.nameplate__tag.label', 'A personal daily · typeset by software', h('span.opt', ' · finite by design')),
    h(`${tag}.nameplate__row`, h('a.nameplate__name', { href: '#/' }, 'First Light'), h('span.sun', { 'aria-hidden': 'true' })));
}

function navRow() {
  const clipped = Object.keys(store.clippings()).length;
  const items = NAV.map((item) => h('li', h('a', { href: item.href, 'aria-current': state.nav === item.id ? 'page' : null },
    item.name,
    item.id === 'wire' && state.wireNew > 0 && h('span.nav__count', h('span.unread', { 'aria-hidden': 'true' }), String(state.wireNew), h('span.vh', ' new')),
    item.id === 'clippings' && clipped > 0 && h('span.nav__count', String(clipped)),
    h('kbd', { 'aria-hidden': 'true' }, item.key))));
  const input = h('input#q', { type: 'search', placeholder: 'Search every edition', autocomplete: 'off', 'data-search': true, onfocus: warm });
  const form = h('form.search', { role: 'search', onsubmit: (event) => { event.preventDefault(); go('/search', { q: input.value.trim() }); input.blur(); } },
    searchGlyph(), h('label.vh', { for: 'q' }, 'Search every edition'), input, h('kbd', { 'aria-hidden': 'true' }, '/'));
  return [
    h('nav.nav', { 'aria-label': 'Primary' }, h('div.wrap.grid.nav__in', h('ul.nav__main', items), form)),
    h('nav.desks', { 'aria-label': 'Desks' }, h('div.wrap.desks__in', h('span.label', 'Desks'),
      h('ul', allDesks().map((d) => h('li', h('a', { href: `#/s/${d.id}`, 'aria-current': state.page?.desk === d.id ? 'page' : null }, h('span.num', d.no), d.name)))))),
  ];
}

function searchGlyph() {
  const svg = arw('find');
  svg.setAttribute('class', 'search__glyph');
  return svg;
}

function earMarkets(quotes, asOf) {
  return h('aside.ear.ear--markets', { 'aria-label': 'Markets at close' },
    h('p.ear__head', h('span.label', 'Markets at close'), quotes.some((q) => q.stale) ? h('span.label.is-stale', 'Stale') : h('span.label', asOf ? shortDate(asOf) : '')),
    h('table.quotes.data', h('tbody', quotes.slice(0, 5).map((q) => h('tr',
      h('th', { scope: 'row' }, q.short || q.name),
      h('td.last-cell', fmtNumber(q.price, q.price < 10 ? 4 : 2, q.currency)),
      h('td.chg-cell', chg(q.changePct)))))));
}

function earEdition(facts) {
  const m = state.manifest;
  const number = String(facts.number ?? '');
  return h('aside.ear.ear--edition', { 'aria-label': 'This edition' },
    h('p.ear__head', h('span.label', 'Edition No.'), h('span.label', facts.next || '')),
    h('div.edition',
      h('p.edition__no', h('span.flap', { role: 'img', 'aria-label': number }, [...number].map((digit) => h('span', digit)))),
      h('div.edition__facts',
        h('p.label', h('b', `${facts.count} ${plural(facts.count, 'story').replace('storys', 'stories')} · ${facts.minutes} min`)),
        h('p.label', `Set ${clock(facts.generatedAt)} ${zoneName()}`),
        h('p.label', m?.counts ? `${m.counts.sourcesOk} of ${m.counts.sources} sources` : ''))));
}

function render() {
  // the masthead is rebuilt when counts change; whatever is being typed in its search box must survive that
  const typed = $('#q');
  const keep = typed ? { value: typed.value, focused: document.activeElement === typed, start: typed.selectionStart, end: typed.selectionEnd } : null;
  const mast = clear($('#mast'));
  const page = state.page || {};
  mast.append(topbar());
  if (page.front) {
    mast.append(h('div.wrap.grid.plate',
      page.front.quotes?.length ? earMarkets(page.front.quotes, page.front.asOf) : h('aside.ear.ear--markets'),
      nameplate('h1'),
      earEdition(page.front)));
  } else {
    mast.append(h('div.wrap.grid.plate.plate--inner', nameplate('p'),
      h('div.plate__title', h('p.label', page.kicker || ''), h('h1.pagehead', page.title || ''))));
  }
  mast.append(...navRow());
  renderTabbar();
  syncTheme();
  document.title = page.front ? `First Light · No. ${page.front.number} · ${longDate(fromDay(page.front.date))}` : `${page.docTitle || page.title || 'First Light'} · First Light`;
  if (keep && (keep.value || keep.focused)) {
    const field = $('#q');
    field.value = keep.value;
    if (keep.focused) { field.focus(); try { field.setSelectionRange(keep.start, keep.end); } catch { /* search inputs may refuse a range */ } }
  }
}

/** Inner pages: a small nameplate and the page title. `desk` highlights a desk in the desk row. */
export function setPage({ title, kicker = '', nav = null, desk = null, docTitle = null }) {
  state.page = { title, kicker, desk, docTitle };
  state.nav = nav;
  render();
}

/** The Front Page: the full plate with both ears. */
export function setFrontPlate(front) {
  state.page = { front };
  state.nav = 'front';
  render();
}

/** "12 of 41 seen" in the top bar, shown only on a front page. */
export function setSeen(seen, total) {
  state.seen = [seen, total];
  const el = $('#seen');
  if (!el) return;
  el.hidden = !total;
  el.textContent = total ? `${seen} of ${total} seen` : '';
}

// ---- phone: tab bar and sheet ---------------------------------------------------------

function renderTabbar() {
  const m = state.manifest;
  const tabs = [
    { id: 'front', name: 'Front', href: '#/', sub: m?.edition ? `No. ${m.edition.number}` : 'Today' },
    { id: 'wire', name: 'Wire', href: '#/wire', sub: state.wireNew ? [h('span.unread'), `${state.wireNew} new`] : 'Live' },
    { id: 'desks', name: 'Desks', sheet: true, sub: '01–10' },
    { id: 'markets', name: 'Markets', href: '#/markets', sub: 'At close' },
    { id: 'more', name: 'More', sheet: 'more', sub: 'Search' },
  ];
  const bar = clear($('#tabbar'));
  const sheetEl = $('#desk-index');
  for (const tab of tabs) {
    const current = tab.sheet ? null : (state.nav === tab.id ? 'page' : null);
    bar.append(tab.sheet
      ? h('a', { href: '#desk-index', role: 'button', 'aria-controls': 'desk-index', dataset: { sheet: String(tab.sheet) },
        'aria-expanded': String(sheetEl.classList.contains('is-open') && sheetEl.dataset.which === String(tab.sheet)),
        onclick: (event) => { event.preventDefault(); toggleSheet(tab.sheet); },
        onkeydown: (event) => { if (event.key === ' ') { event.preventDefault(); toggleSheet(tab.sheet); } } }, tab.name, h('span.label', tab.sub))
      : h('a', { href: tab.href, 'aria-current': current, onclick: () => closeSheet() }, tab.name, h('span.label', tab.sub)));
  }
}

function renderSheet() {
  const sheet = clear($('#desk-index'));
  const input = h('input', { type: 'search', placeholder: 'Search every edition', autocomplete: 'off', 'aria-label': 'Search every edition', onfocus: warm });
  sheet.append(
    h('div.sheet__head', h('p.sheet__title', 'Desks'), h('button.sheet__close.label', { type: 'button', onclick: () => closeSheet(true) }, 'Close')),
    h('form.sheet__search', { role: 'search', onsubmit: (event) => { event.preventDefault(); closeSheet(); go('/search', { q: input.value.trim() }); } }, searchGlyph(), input),
    h('ul.sheet__list', allDesks().map((d) => h('li', h('a', { href: `#/s/${d.id}`, onclick: closeSheet },
      h('span.num', d.no), h('span.name', d.name), h('span.label', ''), arw('right'))))),
    h('div.sheet__more', [['Weekend Review', '#/weekend'], ['Claude Desk', '#/claude'], ['Clippings', '#/clippings'], ['Back Issues', '#/archive'], ['Settings', '#/settings'], ['Colophon', '#/colophon']]
      .map(([name, href]) => h('a', { href, onclick: closeSheet }, name, ' ', arw('right')))));
}

let sheetReturn = null;

function toggleSheet(which) {
  const sheet = $('#desk-index');
  if (sheet.classList.contains('is-open') && sheet.dataset.which === String(which)) { closeSheet(); return; }
  renderSheet();
  sheetReturn = [...$$('#tabbar [data-sheet]')].find((tab) => tab.dataset.sheet === String(which)) || null;
  sheet.dataset.which = String(which);
  sheet.classList.add('is-open');
  document.body.classList.add('sheet-open');
  for (const tab of $$('#tabbar [data-sheet]')) tab.setAttribute('aria-expanded', String(tab.dataset.sheet === String(which)));
  if (which === 'more') $('.sheet__search input', sheet)?.focus();
  else $('.sheet__close', sheet)?.focus();
}

/** `restore` (Escape, Close) puts focus back on the tab that opened the sheet; a navigation leaves it to the view. */
export function closeSheet(restore = false) {
  const sheet = $('#desk-index');
  const inside = sheet.contains(document.activeElement);
  sheet.classList.remove('is-open');
  document.body.classList.remove('sheet-open');
  for (const tab of $$('#tabbar [data-sheet]')) tab.setAttribute('aria-expanded', 'false');
  // never leave focus on a control that is no longer shown
  if (inside && restore === true && sheetReturn) sheetReturn.focus();
  else if (inside) document.activeElement.blur();
}

// ---- footer ------------------------------------------------------------------------------

const KEYS = [
  ['Front Page', 'F'], ['The Wire', 'W'], ['Markets', 'M'], ['Weekend Review', 'R'], ['Claude Desk', 'C'], ['Clippings', 'L'],
  ['Next / previous story', 'J K'], ['Open at source', 'O'], ['Clip it', 'S'], ['Mark read', 'X'],
  ['Search', '/'], ['Go to anything', '⌘ K'], ['Night edition', 'N'],
];

function renderFooter() {
  clear($('#colophon')).append(h('div.wrap.grid.colophon__in',
    h('div.colophon__col.colophon__col--wide',
      h('p.colophon__name', 'First Light'),
      h('p', 'One edition every morning. It is frozen when it is set and it ends. Anything that happens after that is on The Wire.'),
      h('p', 'Headline size is not decoration: it is the number of outlets that carried the story.')),
    h('div.colophon__col.colophon__col--narrow', h('span.label', 'The paper'),
      h('ul', [...NAV.map((item) => [item.name, item.href]), ['Back Issues', '#/archive'], ['Search', '#/search'], ['Settings', '#/settings'], ['Colophon', '#/colophon']]
        .map(([name, href]) => h('li', h('a', { href }, name))))),
    h('div.colophon__col.colophon__keys', h('span.label', 'Keys'),
      h('ul', KEYS.map(([what, keys]) => h('li', h('span', what), h('span', keys.split(' ').map((key) => h('kbd', key))))))),
    h('div.colophon__col', h('span.label', 'Colophon'),
      h('p', 'Set in Archivo and Martian Mono, both open licence, both served from this site.'),
      h('p', 'No tracking, no accounts, no article text: headlines, a line of summary and a link to the source. What you read and clip stays in this browser.'),
      h('p', h('a.more', { href: '#/colophon' }, h('b', 'How it is made, and source health'), arw('right'))))));
}

// ---- keys -------------------------------------------------------------------------------------

const typing = (target) => /^(input|textarea|select)$/i.test(target.tagName) || target.isContentEditable;
let viewKeys = {};

/** A view may claim extra single keys for as long as it is on screen: setViewKeys({u: fn}). */
export function setViewKeys(map) { viewKeys = map || {}; }

function moveCursor(step) {
  const links = $$('#view [data-hl]').filter((el) => el.offsetParent !== null);
  if (!links.length) return;
  const at = links.indexOf(document.activeElement);
  const next = links[Math.max(0, Math.min(links.length - 1, at < 0 ? (step > 0 ? 0 : links.length - 1) : at + step))];
  next.focus({ preventScroll: true });
  next.scrollIntoView({ block: 'nearest' });
}

const focusedItem = () => document.activeElement?.closest?.('[data-story]');

function onKey(event) {
  if (event.defaultPrevented) return;
  const key = event.key;
  if ((event.metaKey || event.ctrlKey) && key.toLowerCase() === 'k') { event.preventDefault(); openPalette(); return; }
  if (key === 'Escape') {
    if (!$('#palette').hidden) { closePalette(); return; }
    if ($('#desk-index').classList.contains('is-open')) { closeSheet(true); return; }
    if (typing(event.target)) event.target.blur();
    return;
  }
  if (event.metaKey || event.ctrlKey || event.altKey || typing(event.target) || !$('#palette').hidden) return;
  const lower = key.toLowerCase();
  if (viewKeys[lower]) { event.preventDefault(); viewKeys[lower](event); return; }
  const item = NAV.find((entry) => entry.key.toLowerCase() === lower);
  if (item) { event.preventDefault(); location.hash = item.href; return; }
  const actions = {
    '/': () => { const field = $('#view [data-find]') || $('#q'); field?.focus(); field?.select?.(); },
    j: () => moveCursor(1),
    k: () => moveCursor(-1),
    o: () => { const link = document.activeElement?.matches?.('[data-hl]') ? document.activeElement : null; link?.click(); },
    s: () => focusedItem()?.querySelector('.clipper')?.click(),
    x: () => { const el = focusedItem(); if (el) { const read = !el.classList.contains('is-read'); store.markRead(el.dataset.story, read); el.classList.toggle('is-read', read); } },
    n: toggleTheme,
    b: () => go('/archive'),
    '?': () => go('/colophon'),
  };
  if (actions[lower]) { event.preventDefault(); actions[lower](); }
}

// ---- palette (⌘K) ---------------------------------------------------------------------------------

function commands() {
  return [
    ...NAV.map((item) => ({ label: item.name, hint: item.key, run: () => { location.hash = item.href; } })),
    ...allDesks().map((d) => ({ label: `${d.no} ${d.name}`, hint: 'Desk', run: () => go(`/s/${d.id}`) })),
    { label: 'Back Issues', hint: 'B', run: () => go('/archive') },
    { label: 'Claude Desk: what’s new', hint: '', run: () => go('/claude/updates') },
    { label: 'Claude Desk: playbook', hint: '', run: () => go('/claude/playbook') },
    { label: 'Claude Desk: recipes', hint: '', run: () => go('/claude/recipes') },
    { label: 'Settings', hint: '', run: () => go('/settings') },
    { label: 'Colophon and source health', hint: '?', run: () => go('/colophon') },
    { label: currentTheme() === 'dark' ? 'Switch to the day edition' : 'Switch to the night edition', hint: 'N', run: toggleTheme },
  ];
}

let paletteReturn = null;

export function openPalette() {
  const box = $('#palette');
  if (!box.hidden) { $('.palette__input', box)?.focus(); return; }
  paletteReturn = document.activeElement;
  const input = h('input.palette__input', { type: 'text', placeholder: 'Go to a page or desk, or type to search', 'aria-label': 'Go to', autocomplete: 'off',
    role: 'combobox', 'aria-expanded': 'true', 'aria-controls': 'palette-list', 'aria-autocomplete': 'list' });
  const list = h('ul.palette__list#palette-list', { role: 'listbox', 'aria-label': 'Places and actions' });
  let options = [];
  let active = 0;
  const paint = () => {
    const query = input.value.trim().toLowerCase();
    options = commands().filter((command) => !query || command.label.toLowerCase().includes(query));
    if (query) options.push({ label: `Search every edition for “${input.value.trim()}”`, hint: '↵', run: () => go('/search', { q: input.value.trim() }) });
    active = Math.min(active, Math.max(0, options.length - 1));
    input.setAttribute('aria-activedescendant', options.length ? `palette-option-${active}` : '');
    clear(list).append(...options.map((option, index) => h('li', { role: 'option', id: `palette-option-${index}`, 'aria-selected': String(index === active),
      onclick: () => { closePalette(); option.run(); }, onmousemove: () => { if (active !== index) { active = index; paint(); } } },
    h('span', option.label), option.hint && h('kbd', option.hint))));
    list.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: 'nearest' });
  };
  input.addEventListener('input', () => { active = 0; paint(); });
  input.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowDown') { event.preventDefault(); active = Math.min(options.length - 1, active + 1); paint(); }
    else if (event.key === 'ArrowUp') { event.preventDefault(); active = Math.max(0, active - 1); paint(); }
    else if (event.key === 'Enter') { event.preventDefault(); const option = options[active]; closePalette(); option?.run(); }
    else if (event.key === 'Tab') { event.preventDefault(); } // the palette is modal: focus stays in its one field
  });
  clear(box).append(h('div.palette__box', input, list));
  box.hidden = false;
  box.onclick = (event) => { if (event.target === box) closePalette(); };
  paint();
  input.focus();
}

export function closePalette() {
  const box = $('#palette');
  if (box.hidden) return;
  box.hidden = true;
  clear(box);
  paletteReturn?.focus?.();
}

// ---- boot ---------------------------------------------------------------------------------------------

/** How many stories on the Wire are newer than the reader's last look at it. */
async function countWireNew() {
  const hot = await data.loadOr('latest.json', { stories: [] });
  // A first-time reader has seen nothing, but "500 new" says nothing either: count from this morning's edition instead.
  const edition = state.manifest?.edition ? await data.loadOr(`editions/${state.manifest.edition.date}.json`, {}) : {};
  const parsed = Date.parse(edition.generatedAt);
  const editionAt = Number.isFinite(parsed) ? parsed : 0;
  const since = store.get('visit', {}).wireSeenAt || editionAt || Date.now() - 6 * 3600000;
  return hot.stories.filter((story) => Date.parse(story.updatedAt || story.publishedAt) > since).length;
}

export async function refreshWireCount() {
  const count = Math.min(999, await countWireNew());
  if (count !== state.wireNew) { state.wireNew = count; render(); }
}

export function init(manifest) {
  state.manifest = manifest;
  renderFooter();
  renderSheet();
  document.addEventListener('keydown', onKey);
  store.subscribe('saved', () => render());
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', syncTheme);
  window.addEventListener('hashchange', () => {
    if (location.hash && !location.hash.startsWith('#/')) return; // an in-page anchor, not a navigation
    closeSheet(); closePalette(); setViewKeys(null);
  });
  // the skip link moves focus to the page; it must not be read as a route
  $('.skip')?.addEventListener('click', (event) => { event.preventDefault(); $('#view').focus(); $('#view').scrollIntoView(); });
  store.onStorageFull(() => toast('This browser’s storage is full or blocked: reading state and clippings will not be kept.'));
  if (manifest) refreshWireCount();
}
