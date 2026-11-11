// The typesetter: shared pieces every page is set from. Class names come from css/bulletin.css.

import { h, s, arw, outLink } from './dom.js';
import * as store from './store.js';
import { stamp } from './time.js';
import { buildHash } from './router.js';

// ---- desks ----------------------------------------------------------------

let desks = [];

/** Sections from the manifest become numbered desks: 01 World, 02 India, … */
export function setDesks(sections) {
  desks = (sections || []).map((section, index) => ({ ...section, no: String(index + 1).padStart(2, '0') }));
}

export const allDesks = () => desks;
export const desk = (id) => desks.find((d) => d.id === id) || { id, name: id || 'News', no: '··' };

// ---- text -----------------------------------------------------------------

/** Typesetter's quotes and dashes: feeds send typewriter ones. */
export function smart(text) {
  return String(text ?? '')
    .replace(/(\w)'(\w)/g, '$1’$2')
    .replace(/(^|[\s(\[])"/g, '$1“')
    .replace(/"/g, '”')
    .replace(/(^|[\s(\[])'/g, '$1‘')
    .replace(/'/g, '’')
    .replace(/ - | — /g, ' – ');
}

/** A headline as nodes: typeset, and never broken inside a compound such as 10-year. */
export function headline(text) {
  return smart(text).split(/(\d[\d,.]*-[A-Za-z]+)/).map((piece, index) => (index % 2 ? h('span.nb', piece) : piece));
}

const ABBREVIATIONS = /\b(Dr|Mr|Mrs|Ms|St|Prof|Rs|No|vs|Inc|Ltd|Co|Corp|Jr|Sr|U\.S|U\.K)\.\s/g;

/** Split a summary into sentences; abbreviations do not end one. */
export function sentences(text) {
  const guarded = String(text || '').trim().replace(ABBREVIATIONS, (match) => `${match.trimEnd()}\u0000`);
  return guarded.split(/(?<=[.!?…]["”’]?)\s+(?=[A-Z“‘"'\d])/).map((part) => part.replace(/\u0000/g, ' ').trim()).filter(Boolean);
}

/**
 * Whole sentences only, at most `count`. A feed blurb cut off mid-sentence is dropped rather
 * than printed with a dangling end, unless it is short enough to stand as a deck line.
 */
export function summarize(text, count = 2) {
  const raw = String(text || '').trim();
  if (!raw) return '';
  const parts = sentences(raw);
  const whole = parts.filter((part) => /[.!?]["”’]?$/.test(part));
  if (whole.length) return smart(whole.slice(0, count).join(' '));
  if (parts.length === 1 && raw.length < 200) return smart(raw.replace(/\s*(…|\.\.\.)$/, '')) + (/(…|\.\.\.)$/.test(raw) ? ' …' : '');
  return '';
}

export const plural = (n, word) => `${word}${n === 1 ? '' : 's'}`;

/** A figure with digit grouping: Indian grouping for rupee amounts (1,02,345), Western for everything else. */
export function fmtNumber(value, digits = 2, currency = null) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '–';
  return Number(value).toLocaleString(currency === 'INR' ? 'en-IN' : 'en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

// ---- coverage: the one idea -------------------------------------------------

/** Coverage tier from the number of outlets: 4 = nine or more, 3 = six to eight, 2 = three to five, 1 = one or two. */
export const tier = (n) => (n >= 9 ? 4 : n >= 6 ? 3 : n >= 3 ? 2 : 1);
export const FRONT_STEP = { 4: 'hl-5', 3: 'hl-4', 2: 'hl-3', 1: 'hl-1' };
export const DESK_STEP = { 4: 'hl-4', 3: 'hl-3', 2: 'hl-2', 1: 'hl-1' };
export const WIDE_STEP = { 4: 'hl-5', 3: 'hl-4', 2: 'hl-3', 1: 'hl-1' };
export const RAIL_STEP = { 4: 'hl-6', 3: 'hl-5', 2: 'hl-4', 1: 'hl-2' };
export const RAIL_SPAN = { 4: 'span-5', 3: 'span-4', 2: 'span-3', 1: 'span-3' };

export const ticks = (n) => h('span.ticks', { style: `--n:${Math.max(1, Math.min(n, 12))}`, 'aria-hidden': 'true' });

export const storyHref = (story) => buildHash(`/story/${story.id}`, { d: story.day });

/** The small coverage mark. It links to the story's own page, where every outlet is listed. */
export function covSmall(story, extraClass = '') {
  const n = story.sourceCount || 1;
  return h(`a.cov${extraClass}`, { href: storyHref(story), title: `Carried by ${n} ${plural(n, 'outlet')}: see who` },
    ticks(n), h('span', h('b', String(n)), ` ${plural(n, 'outlet')}`));
}

export function covLarge(story) {
  const n = story.sourceCount || 1;
  return h('a.cov-l', { href: storyHref(story), title: `Carried by ${n} ${plural(n, 'outlet')}: see who` },
    h('span.cov-l__n', String(n)), ticks(n), h('span.label', h('b', plural(n, 'outlet'))));
}

/** The big numeral that closes the first column of a wide desk. */
export function covFoot(story) {
  const n = story.sourceCount || 1;
  const first = story.sources?.[0]?.name || '';
  const others = n === 1 ? 'alone' : `+ ${n - 1} ${plural(n - 1, 'other')}`;
  return h(`p.cov-foot${n >= 10 ? '.cov-foot--wide' : ''}`, { title: `Carried by ${n} ${plural(n, 'outlet')}` },
    h('span.cov-foot__n', String(n)),
    h('span.cov-foot__what', ticks(n), h('span.label', h('b', plural(n, 'outlet'), h('br'), 'carried', h('br'), 'this'))),
    h('span.cov-foot__who.label', first, h('br'), others));
}

// ---- stories ----------------------------------------------------------------

// One story can have two clip buttons on a page (top of the desk and the desk's wire); they must agree.
const clipPainters = new WeakMap();
store.subscribe('saved', () => {
  for (const button of document.querySelectorAll('.clipper')) clipPainters.get(button)?.();
});

export const storyKey = (story) => `story:${story.id}`;

export function storySnapshot(story) {
  return {
    kind: 'story', id: story.id, title: story.title, url: story.url, day: story.day,
    source: story.sources?.[0]?.name || '', section: story.section, sourceCount: story.sourceCount, at: story.publishedAt,
  };
}

/** A clip toggle. `compact` renders the bare word; otherwise a label-styled button. */
export function clipButton(key, snapshot, { label = 'Clip', done = 'Clipped' } = {}) {
  const button = h('button.clipper.label', { type: 'button', 'aria-pressed': String(store.isClipped(key)) });
  clipPainters.set(button, () => paint());
  const paint = () => {
    const on = store.isClipped(key);
    button.setAttribute('aria-pressed', String(on));
    button.replaceChildren(h('b', on ? done : label));
    button.title = on ? 'Remove from Clippings' : 'Keep in Clippings';
  };
  button.addEventListener('click', (event) => {
    event.preventDefault();
    event.stopPropagation();
    store.toggleClip(key, snapshot); // every clip button on the page repaints through the store subscription below
  });
  paint();
  return button;
}

/**
 * One story, set at the step its coverage earned.
 * opts: step (class), cov 's'|'l'|'foot', showSum, clamp (lines), deskTag, tag, cls, day (reference day for the stamp).
 */
export function storyCard(story, opts = {}) {
  const { step = 'hl-2', cov = 's', showSum = true, clamp = null, deskTag = false, tag = 'h3', cls = '', day = story.day } = opts;
  const n = story.sourceCount || 1;
  const summary = showSum ? summarize(story.summary) : '';
  const time = h('time', { datetime: story.publishedAt }, stamp(story.updatedAt || story.publishedAt, day));
  const d = desk(story.section);
  const right = deskTag ? h('span', h('b', d.no), ` ${d.name} · `, time) : time;
  let meta;
  if (cov === 'l') {
    meta = h('p.story__meta.story__meta--l.label', covLarge(story), right);
  } else if (cov === 'foot') {
    meta = h('p.story__meta.label',
      h('span.cov.cov--inline', ticks(n), h('span', h('b', String(n)), ` ${plural(n, 'outlet')}`)),
      h('b.top', 'Top of the desk'), right);
  } else {
    meta = h('p.story__meta.label', covSmall(story), right);
  }
  const link = outLink(story.url, { 'data-hl': true, onclick: () => { store.markRead(story.id); article.classList.add('is-read'); } }, headline(story.title));
  const article = h(`article.story${summary ? '' : '.story--bare'}${store.isRead(story.id) ? '.is-read' : ''}`,
    { class: cls, dataset: { outlets: String(n), story: story.id } },
    meta,
    h(`${tag}.story__hl.${step}`, link),
    summary && h(`p.story__sum${clamp ? `.story__sum--clamp${clamp}` : ''}`, summary),
    h('p.story__src.label',
      h('b', story.sources?.[0]?.name || ''), arw('ne'),
      story.thread && h('a.thread', { href: storyHref(story), title: 'A continuing story: see earlier days' }, `Day ${story.thread.day}`),
      clipButton(storyKey(story), storySnapshot(story))));
  return article;
}

// ---- market figures -----------------------------------------------------------

/** A signed change: arrow, sign and words, never colour alone. */
export function chg(pct, { digits = 2, unit = '%' } = {}) {
  if (pct === null || pct === undefined || Number.isNaN(Number(pct))) return h('span.chg.chg--flat', arw('flat'), h('span', '–'));
  const value = Number(pct);
  const text = `${Math.abs(value).toFixed(digits)}${unit}`;
  if (value > 0) return h('span.chg.chg--up', arw('up'), h('span', `+${text}`), h('span.vh', ' up'));
  if (value < 0) return h('span.chg.chg--down', arw('down'), h('span', `−${text}`), h('span.vh', ' down'));
  return h('span.chg.chg--flat', arw('flat'), h('span', text), h('span.vh', ' unchanged'));
}

/** A sparkline of closes. The dotted line is the first close in the window. */
export function spark(values, { w = 100, height = 32, label = '' } = {}) {
  const points = (values || []).filter((v) => typeof v === 'number' && Number.isFinite(v));
  const svg = s('svg', { class: 'spark', viewBox: `0 0 ${w} ${height}`, preserveAspectRatio: 'none', role: 'img', 'aria-label': label });
  if (points.length < 2) return svg;
  const lo = Math.min(...points);
  const hi = Math.max(...points);
  const pad = 3;
  const span = hi - lo || 1;
  const y = (v) => Math.round((height - pad - ((v - lo) / span) * (height - 2 * pad)) * 10) / 10;
  const x = (i) => Math.round(((i * (w - 4)) / (points.length - 1)) * 10) / 10;
  svg.append(
    s('line', { class: 'spark__base', x1: 0, x2: w, y1: y(points[0]), y2: y(points[0]) }),
    s('polyline', { class: 'spark__line', points: points.map((v, i) => `${x(i)},${y(v)}`).join(' ') }),
    s('circle', { class: 'spark__now', cx: w - 4, cy: y(points[points.length - 1]), r: 2.6 }));
  return svg;
}

// ---- page furniture -------------------------------------------------------------

/** The strip under the nav: "Front Page · No. 12 · 41 stories", with an optional right side. */
export function folio(left, right) {
  return h('div.folio.label', h('p', left), right && h('p.folio__key', right));
}

/** A notice set in the page: used for empty, missing and error states. */
export function notice(title, body, action) {
  return h('div.notice', h('p.notice__title', title), body && h('p.notice__body', body), action);
}

/** A row of filter buttons where exactly one (or several, with multi) is pressed. */
export function filterBar(options, selected, onChange, { label = '' } = {}) {
  const bar = h('div.filters', { role: 'group', 'aria-label': label });
  for (const option of options) {
    const pressed = Array.isArray(selected) ? selected.includes(option.id) : selected === option.id;
    bar.append(h('button.chip', {
      type: 'button', 'aria-pressed': String(pressed), class: pressed ? 'chip--solid' : '', title: option.title || null,
      onclick: () => onChange(option.id),
    }, option.label, option.count !== undefined && h('span.chip__n', String(option.count))));
  }
  return bar;
}
