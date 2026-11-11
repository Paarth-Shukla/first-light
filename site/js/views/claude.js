// Claude Desk: what is new in Claude, a playbook of every feature with how to use it, and workplace recipes.
// Adoption state (not tried / tried / in my workflow) is personal and lives in this browser.

import { h, arw, outLink, copyText, trustedHtml, clear, append } from '../core/dom.js';
import * as data from '../core/data.js';
import * as store from '../core/store.js';
import * as shell from '../shell.js';
import { smart, folio, notice, filterBar, clipButton, plural } from '../core/ui.js';
import { shortDate, fromDay, localDate } from '../core/time.js';
import { replaceQuery } from '../core/router.js';

const DAY = 86400000;
const LEITNER = [1, 3, 7, 21]; // days until a "tried" technique comes back for another go
const STATES = [['none', 'Not tried'], ['tried', 'Tried'], ['habit', 'In my workflow']];
const SURFACE_TAG = { apps: 'Apps', code: 'Code', platform: 'API', cowork: 'Cowork', integrations: 'Tools', models: 'Models', news: 'News', learn: 'Learn' };
const LEVELS = { starter: 'Starter', intermediate: 'Intermediate', power: 'Power user' };

// ---- adoption state --------------------------------------------------------------

export const adoption = () => store.get('claude', {});
export const stateOf = (id) => adoption()[id]?.state || 'none';

function setState(id, next) {
  store.update('claude', {}, (map) => {
    const previous = map[id] || { box: 0 };
    if (next === 'none') { delete map[id]; return map; }
    const box = next === 'tried' ? Math.min(LEITNER.length - 1, previous.state === 'tried' ? previous.box + 1 : 0) : previous.box || 0;
    map[id] = { state: next, at: Date.now(), box, due: next === 'tried' ? Date.now() + LEITNER[box] * DAY : null };
    return map;
  });
}

/** The three-way "where are you with this?" control. `scope` keeps radio groups on one page apart. */
export function adoptControl(id, scope = 'x', paper = false) {
  const name = `adopt-${scope}-${id}`;
  const current = stateOf(id);
  return h('div.adopt',
    h('span.label', { id: `${name}-l` }, 'Where are you with this?'),
    h(`div.seg${paper ? '.seg--paper' : ''}`, { role: 'radiogroup', 'aria-labelledby': `${name}-l` },
      STATES.map(([value, label]) => h('label', h('input', { type: 'radio', name, value, checked: value === current,
        onchange: () => { setState(id, value); if (value === 'tried') shell.toast(`Noted. It will come back in ${LEITNER[adoption()[id].box]} ${plural(LEITNER[adoption()[id].box], 'day')}.`); } }), h('span', label)))));
}

const lowerFirst = (text) => (/^[A-Z][a-z]/.test(text) ? text[0].toLowerCase() + text.slice(1) : text);

/** "Reach for it when …": cards are written as "Use it when …" or as a plain sentence; both read cleanly here. */
export function whenLine(text) {
  const clean = smart(String(text || '').trim());
  const lead = /^(?:use|reach for|choose|pick|turn to) (?:it|one|this|them|these)(?: instead)? (when|for|to|if|whenever)\s+/i.exec(clean);
  if (lead) {
    const rest = clean.slice(lead[0].length);
    const joiner = lead[1].toLowerCase();
    return h('p.claude__when', h('b', joiner === 'when' || joiner === 'whenever' || joiner === 'if' ? 'Reach for it when ' : `Reach for it ${joiner} `), rest);
  }
  if (/^when\s/i.test(clean)) return h('p.claude__when', h('b', 'Reach for it when '), clean.replace(/^when\s+/i, ''));
  return h('p.claude__when', h('b', 'When to reach for it. '), clean);
}

/** A copyable prompt, command or config. {{slots}} and [SLOTS] are set off so they are easy to spot. */
export function promptBlock(text, kind = 'prompt', title = null) {
  const pieces = String(text || '').split(/(\{\{[^}\n]+\}\}|\[[A-Z][A-Z0-9 _/-]{2,}\]|<[a-z][a-z0-9 _-]{2,}>)/);
  const slots = pieces.filter((_, index) => index % 2).length;
  const label = title || `${{ prompt: 'Prompt', command: 'Command', config: 'Config' }[kind] || 'Prompt'}${slots ? ` · ${slots} ${plural(slots, 'slot')} to fill` : ''}`;
  const word = h('span', 'Copy');
  const button = h('button.copy', { type: 'button', onclick: async () => {
    const ok = await copyText(pre.textContent);
    word.textContent = ok ? 'Copied' : 'Select and copy';
    button.toggleAttribute('data-done', ok);
    setTimeout(() => { word.textContent = 'Copy'; button.removeAttribute('data-done'); }, 2200);
  } }, arw('copy'), word);
  const pre = h('pre', { tabindex: '0' }, pieces.map((piece, index) => (index % 2 ? h('span.slot', piece) : piece)));
  return h('div.prompt', h('div.prompt__bar', h('span.label', label), button), pre);
}

// ---- shared pieces ------------------------------------------------------------------

function subnav(current) {
  const tabs = [['desk', 'The desk', '#/claude'], ['updates', 'What’s new', '#/claude/updates'], ['playbook', 'Playbook', '#/claude/playbook'], ['recipes', 'Recipes', '#/claude/recipes']];
  return h('nav.subnav.label', { 'aria-label': 'Claude Desk' }, tabs.map(([id, name, href]) => h('a', { href, 'aria-current': id === current ? 'page' : null }, h('b', name))));
}

const surfaceName = (book, id) => book.surfaces.find((surface) => surface.id === id)?.name || SURFACE_TAG[id] || id;

/** Today's technique: one that is due again, else the best untried one, rotating daily. */
export function pickDrill(features, now = Date.now()) {
  if (!features.length) return null;
  const states = adoption();
  const due = features.filter((f) => states[f.id]?.state === 'tried' && states[f.id].due && states[f.id].due <= now)
    .sort((a, b) => states[a.id].due - states[b.id].due);
  if (due.length) return { feature: due[0], reason: 'Back for another go', due: true };
  const untried = features.filter((f) => !states[f.id])
    .sort((a, b) => (b.payoff - b.effort) - (a.payoff - a.effort) || a.id.localeCompare(b.id));
  const pool = untried.length ? untried.slice(0, Math.max(7, Math.ceil(untried.length / 4))) : features;
  const dayNumber = Math.floor(fromDay(localDate(now)).getTime() / DAY);
  return { feature: pool[dayNumber % pool.length], reason: untried.length ? 'One technique to try at work today' : 'A refresher' };
}

function drillBlock(pick) {
  if (!pick) return null;
  const f = pick.feature;
  return h('section.claude', { 'aria-labelledby': 'drill-h' },
    h('header.claude__head', h('span.tile', { 'aria-hidden': 'true' }, 'C'), h('h2.claude__name#drill-h', 'Today’s technique'), h('span.label', pick.reason)),
    h('div.claude__pitch',
      h('h3.claude__title', h('a', { href: `#/claude/feature/${f.id}` }, smart(f.title))),
      whenLine(f.when || f.summary),
      adoptControl(f.id, 'drill'),
      // the Tried radio is already set on a technique that has come back, so it needs its own way to log another go
      pick.due && h('p.claude__links', h('button.readon', { type: 'button', onclick: (event) => { setState(f.id, 'tried'); event.target.disabled = true; event.target.textContent = `Logged. Back in ${LEITNER[adoption()[f.id].box]} days`; } }, 'Tried it again'))),
    h('div.claude__work', f.example ? promptBlock(f.example, f.example_kind) : null,
      h('p.claude__links', h('a.readon', { href: `#/claude/feature/${f.id}` }, 'Steps, pitfalls and docs ', arw('right')))));
}

function featureMap(book) {
  const states = adoption();
  const tally = { none: 0, tried: 0, habit: 0 };
  for (const f of book.features) tally[states[f.id]?.state || 'none']++;
  return h('section.block', { 'aria-labelledby': 'map-h' },
    h('header.block__head', h('h2.block__title#map-h', 'Feature map'),
      h('p.label', h('b', `${tally.habit} in my workflow`), ` · ${tally.tried} tried · ${tally.none} not tried`)),
    h('div.fmap', book.surfaces.filter((surface) => book.features.some((f) => f.surface === surface.id)).map((surface) => h('div.fmap__row',
      h('a.fmap__name.label', { href: `#/claude/playbook?surface=${surface.id}` }, h('b', surface.name)),
      h('div.fmap__cells', book.features.filter((f) => f.surface === surface.id).map((f) => h('a.fmap__cell', {
        href: `#/claude/feature/${f.id}`, dataset: { state: states[f.id]?.state || 'none' },
        title: `${f.title}: ${STATES.find(([value]) => value === (states[f.id]?.state || 'none'))[1].toLowerCase()}`,
        'aria-label': `${f.title}, ${STATES.find(([value]) => value === (states[f.id]?.state || 'none'))[1].toLowerCase()}`,
      })))))),
    h('p.fmap__key.label', h('span.fmap__cell', { dataset: { state: 'habit' } }), 'In my workflow', h('span.fmap__cell', { dataset: { state: 'tried' } }), 'Tried', h('span.fmap__cell', { dataset: { state: 'none' } }), 'Not tried'));
}

function updateRow(entry, book, seenAt) {
  // new = dated after the day of the reader's last look (in the paper's calendar); never-visited readers see no marks
  const fresh = seenAt > 0 && entry.date > localDate(seenAt);
  return h('li.row', h('span.row__meta',
    fresh ? h('span.unread', { title: 'New since your last visit' }) : h('span.unread.unread--off'),
    h('time.row__date', { datetime: entry.date }, shortDate(fromDay(entry.date))),
    h('span.tag.label', SURFACE_TAG[entry.surface] || entry.surface)),
  h('div.row__main',
    h('p.row__title', outLink(entry.url, { 'data-hl': true }, smart(entry.title))),
    entry.summary && h('p.row__sum', smart(entry.summary))),
  h('p.row__aside.label', (entry.features || []).slice(0, 2).map((id) => {
    const feature = book.features.find((f) => f.id === id);
    return feature && h('a.more', { href: `#/claude/feature/${id}` }, h('b', feature.title), arw('right'));
  })));
}

// ---- pages ------------------------------------------------------------------------------

export async function claudeHome(el, params, ctx) {
  ctx.setPage({ title: 'Claude Desk', kicker: 'Get more out of Claude at work', nav: 'claude' });
  const [book, news] = await Promise.all([data.playbook(), data.updates()]);
  const seenAt = store.get('visit', {}).claudeSeenAt || 0;
  const wrap = h('div.wrap.page', subnav('desk'),
    folio([h('b', 'Claude Desk'), ` · ${book.features.length} techniques · ${book.recipes.length} recipes · ${news.entries.length} updates on file`],
      news.status && [h('span', { title: 'From the Claude status page' }, `Claude status: ${news.status.description}`)]));
  if (!book.features.length && !news.entries.length) {
    wrap.append(notice('The Claude Desk has not been built yet.', 'Run the pipeline’s claude stage to fetch release notes and compile the playbook.'));
    el.append(wrap);
    return;
  }
  let map = book.features.length ? featureMap(book) : null;
  append(wrap, drillBlock(pickDrill(book.features)), map);
  // the adoption control above the map changes what the map shows: keep it current
  const stopMap = map ? store.subscribe('claude', () => { const next = featureMap(book); map.replaceWith(next); map = next; }) : null;
  wrap.append(h('section.block', { 'aria-labelledby': 'new-h' },
    h('header.block__head', h('h2.block__title#new-h', 'What’s new'), h('a.more.label', { href: '#/claude/updates' }, h('b', `All ${news.entries.length}`), arw('right'))),
    news.entries.length ? h('ol.rows', news.entries.slice(0, 8).map((entry) => updateRow(entry, book, seenAt))) : h('p.block__empty', 'No release notes fetched yet.')));
  const starters = book.recipes.filter((r) => r.level === 'starter').slice(0, 6);
  if (book.recipes.length) {
    wrap.append(h('section.block', { 'aria-labelledby': 'rec-h' },
      h('header.block__head', h('h2.block__title#rec-h', 'Recipes for the working week'), h('a.more.label', { href: '#/claude/recipes' }, h('b', `All ${book.recipes.length}`), arw('right'))),
      h('ol.rows', (starters.length ? starters : book.recipes.slice(0, 6)).map((r) => recipeRow(r, book)))));
  }
  el.append(wrap);
  return () => stopMap?.();
}

export async function claudeUpdates(el, params, ctx) {
  ctx.setPage({ title: 'What’s new in Claude', kicker: 'Claude Desk', nav: 'claude' });
  const [book, news] = await Promise.all([data.playbook(), data.updates()]);
  const seenAt = store.get('visit', {}).claudeSeenAt || 0;
  let surface = params.query.surface || 'all';
  const list = h('ol.rows');
  const bar = h('div');
  const surfaces = [...new Set(news.entries.map((entry) => entry.surface))];
  const paint = () => {
    const shown = news.entries.filter((entry) => surface === 'all' || entry.surface === surface);
    clear(bar).append(filterBar([{ id: 'all', label: 'Everything', count: news.entries.length },
      ...surfaces.map((id) => ({ id, label: surfaceName(book, id), count: news.entries.filter((entry) => entry.surface === id).length }))],
    surface, (id) => { surface = id; replaceQuery({ surface: id === 'all' ? null : id }); paint(); }, { label: 'Filter by product' }));
    clear(list).append(...shown.slice(0, 250).map((entry) => updateRow(entry, book, seenAt)));
  };
  paint();
  el.append(h('div.wrap.page', subnav('updates'),
    folio([h('b', 'What’s new'), ` · ${news.entries.length} updates from release notes, changelogs and the Claude blog`], news.generatedAt && [h('span', `Fetched ${shortDate(news.generatedAt)}`)]),
    bar, news.entries.length ? list : notice('No updates fetched yet.', 'The claude stage of the pipeline fills this page.')));
  return () => store.update('visit', {}, (visit) => ({ ...visit, claudeSeenAt: Date.now() }));
}

function featureRow(f) {
  const state = stateOf(f.id);
  return h('li.row', { dataset: { story: `feature:${f.id}` } },
    h('span.row__meta', h('span.fmap__cell', { dataset: { state }, title: STATES.find(([value]) => value === state)[1] }),
      h('span.tag.label', LEVELS[f.level] || f.level), f.status !== 'stable' && h('span.tag.tag--spot.label', f.status)),
    h('div.row__main', h('p.row__title', h('a', { href: `#/claude/feature/${f.id}`, 'data-hl': true }, smart(f.title))), h('p.row__sum', smart(f.summary || ''))),
    h('p.row__aside.label', `Payoff ${'●'.repeat(f.payoff || 1)}${'○'.repeat(3 - (f.payoff || 1))}`, h('br'), `Effort ${'●'.repeat(f.effort || 1)}${'○'.repeat(3 - (f.effort || 1))}`));
}

export async function claudePlaybook(el, params, ctx) {
  ctx.setPage({ title: 'The Playbook', kicker: 'Claude Desk', nav: 'claude' });
  const book = await data.playbook();
  const filters = { surface: params.query.surface || 'all', job: params.query.job || 'all', state: params.query.state || 'all', q: params.query.q || '' };
  const body = h('div');
  const bars = h('div.filterset');
  const input = h('input.quickfind', { type: 'search', placeholder: 'Filter techniques', value: filters.q, 'aria-label': 'Filter techniques', 'data-find': true,
    oninput: () => { filters.q = input.value; sync(); paintList(); } });
  const sync = () => replaceQuery({ surface: filters.surface === 'all' ? null : filters.surface, job: filters.job === 'all' ? null : filters.job, state: filters.state === 'all' ? null : filters.state, q: filters.q || null });
  const matches = (f) => (filters.surface === 'all' || f.surface === filters.surface)
    && (filters.job === 'all' || (f.jobs || []).includes(filters.job))
    && (filters.state === 'all' || stateOf(f.id) === filters.state)
    && (!filters.q || `${f.title} ${f.summary} ${(f.tags || []).join(' ')}`.toLowerCase().includes(filters.q.toLowerCase()));
  const paintList = () => {
    const shown = book.features.filter(matches);
    clear(body);
    if (!shown.length) { body.append(notice('No technique matches these filters.', null, h('button.readon', { type: 'button', onclick: () => { Object.assign(filters, { surface: 'all', job: 'all', state: 'all', q: '' }); input.value = ''; sync(); paint(); } }, 'Clear the filters'))); return; }
    for (const surface of book.surfaces) {
      const inSurface = shown.filter((f) => f.surface === surface.id);
      if (!inSurface.length) continue;
      const groups = [...new Set(inSurface.map((f) => f.group || 'General'))];
      body.append(h('section.block', h('header.block__head', h('h2.block__title', surface.name), h('span.label', `${inSurface.length} ${plural(inSurface.length, 'technique')}`)),
        groups.map((group) => [h('h3.block__sub.label', h('b', group)), h('ol.rows', inSurface.filter((f) => (f.group || 'General') === group).map(featureRow))])));
    }
  };
  const paint = () => {
    const pick = (key) => (id) => { filters[key] = id; sync(); paint(); };
    clear(bars).append(
      filterBar([{ id: 'all', label: 'Every product' }, ...book.surfaces.filter((s) => book.features.some((f) => f.surface === s.id)).map((s) => ({ id: s.id, label: s.name }))], filters.surface, pick('surface'), { label: 'Product' }),
      filterBar([{ id: 'all', label: 'Any job' }, ...book.jobs.filter((j) => book.features.some((f) => (f.jobs || []).includes(j.id))).map((j) => ({ id: j.id, label: j.name }))], filters.job, pick('job'), { label: 'Job' }),
      filterBar([{ id: 'all', label: 'Any state' }, ...STATES.map(([id, label]) => ({ id, label }))], filters.state, pick('state'), { label: 'Where you are with it' }));
    paintList();
  };
  paint();
  el.append(h('div.wrap.page', subnav('playbook'),
    folio([h('b', 'Playbook'), ` · ${book.features.length} techniques, each checked against the official docs`]),
    book.features.length ? [h('div.findrow', input), bars, body] : notice('The playbook has not been compiled yet.')));
}

export async function claudeFeature(el, params, ctx) {
  const [book, news] = await Promise.all([data.playbook(), data.updates()]);
  const f = book.features.find((item) => item.id === params.id);
  if (!f) {
    ctx.setPage({ title: 'Not in the playbook', kicker: 'Claude Desk', nav: 'claude' });
    el.append(h('div.wrap.page', subnav('playbook'), notice('That technique is not in the playbook.', 'It may have been renamed.', h('a.readon', { href: '#/claude/playbook' }, 'Open the playbook ', arw('right')))));
    return;
  }
  ctx.setPage({ title: f.title, kicker: `Claude Desk · ${surfaceName(book, f.surface)}`, nav: 'claude' });
  const recipes = book.recipes.filter((r) => (r.features || []).includes(f.id));
  const related = news.entries.filter((entry) => (entry.features || []).includes(f.id)).slice(0, 5);
  const stale = f.verified && (Date.now() - fromDay(f.verified).getTime()) / DAY > 90;
  el.append(h('div.wrap.page', subnav('playbook'),
    h('article.claude.claude--paper',
      h('header.claude__head', h('span.tile', { 'aria-hidden': 'true' }, 'C'), h('p.claude__name', surfaceName(book, f.surface)),
        h('span.label', [f.group, LEVELS[f.level], f.status !== 'stable' ? f.status : null].filter(Boolean).join(' · '))),
      h('div.claude__pitch',
        h('h2.claude__title', smart(f.title)),
        h('p.claude__when', smart(f.summary || '')),
        f.when && whenLine(f.when),
        f.replaces && h('p.claude__when', h('b', 'It replaces '), lowerFirst(smart(f.replaces))),
        adoptControl(f.id, 'page', true),
        h('p.claude__links', clipButton(`feature:${f.id}`, { kind: 'feature', id: f.id, title: f.title, url: `#/claude/feature/${f.id}`, source: 'Claude Desk' }))),
      h('div.claude__work', f.example ? promptBlock(f.example, f.example_kind) : null)),
    h('div.grid.detail',
      h('div.prose.detail__main', trustedHtml(stripExample(f.html))),
      h('aside.detail__side',
        h('h3.label', h('b', 'Official docs')),
        h('ul.linklist', (f.docs || []).map((doc) => h('li', outLink(doc.url, {}, smart(doc.title), ' ', arw('ne'))))),
        f.verified && h(`p.label${stale ? '.is-stale' : ''}`, `Checked against the docs on ${shortDate(fromDay(f.verified))}${stale ? ' · may be out of date' : ''}`),
        recipes.length ? [h('h3.label', h('b', 'Recipes that use it')), h('ul.linklist', recipes.map((r) => h('li', h('a', { href: `#/claude/recipe/${r.id}` }, smart(r.title), ' ', arw('right')))))] : null,
        related.length ? [h('h3.label', h('b', 'Recent changes')), h('ul.linklist', related.map((entry) => h('li', outLink(entry.url, {}, `${shortDate(fromDay(entry.date))}: ${smart(entry.title)} `, arw('ne')))))] : null,
        (f.tags || []).length ? h('p.label', (f.tags || []).map((tag) => h('a.tagword', { href: `#/claude/playbook?q=${encodeURIComponent(tag)}` }, `#${tag}`))) : null))));
}

/** The example already sits in the prompt block; drop its copy from the body. */
function stripExample(html) {
  return String(html || '').replace(/<h2>Example<\/h2>\s*<pre>[\s\S]*?<\/pre>/, '');
}

function recipeRow(r, book) {
  const job = book.jobs.find((j) => j.id === r.job)?.name || r.job;
  return h('li.row', h('span.row__meta', h('span.tag.label', job), h('span.tag.label', LEVELS[r.level] || r.level)),
    h('div.row__main', h('p.row__title', h('a', { href: `#/claude/recipe/${r.id}`, 'data-hl': true }, smart(r.title))),
      h('p.row__sum', `Uses ${(r.features || []).map((id) => book.features.find((f) => f.id === id)?.title || id).slice(0, 4).join(', ')}`)),
    h('p.row__aside.label', r.minutes_saved ? [h('b', `${r.minutes_saved} min`), h('br'), 'saved each time'] : null));
}

export async function claudeRecipes(el, params, ctx) {
  ctx.setPage({ title: 'Recipes', kicker: 'Claude Desk', nav: 'claude' });
  const book = await data.playbook();
  let job = params.query.job || 'all';
  const list = h('div');
  const bar = h('div');
  const paint = () => {
    clear(bar).append(filterBar([{ id: 'all', label: 'Every job', count: book.recipes.length },
      ...book.jobs.filter((j) => book.recipes.some((r) => r.job === j.id)).map((j) => ({ id: j.id, label: j.name, count: book.recipes.filter((r) => r.job === j.id).length }))],
    job, (id) => { job = id; replaceQuery({ job: id === 'all' ? null : id }); paint(); }, { label: 'Filter by job' }));
    clear(list).append(h('ol.rows', book.recipes.filter((r) => job === 'all' || r.job === job).map((r) => recipeRow(r, book))));
  };
  paint();
  el.append(h('div.wrap.page', subnav('recipes'),
    folio([h('b', 'Recipes'), ` · ${book.recipes.length} end-to-end jobs, each with a prompt to fill in`]),
    book.recipes.length ? [bar, list] : notice('No recipes have been compiled yet.')));
}

export async function claudeRecipe(el, params, ctx) {
  const book = await data.playbook();
  const r = book.recipes.find((item) => item.id === params.id);
  if (!r) {
    ctx.setPage({ title: 'No such recipe', kicker: 'Claude Desk', nav: 'claude' });
    el.append(h('div.wrap.page', subnav('recipes'), notice('That recipe is not on file.', null, h('a.readon', { href: '#/claude/recipes' }, 'All recipes ', arw('right')))));
    return;
  }
  ctx.setPage({ title: r.title, kicker: `Claude Desk · Recipe · ${book.jobs.find((j) => j.id === r.job)?.name || r.job}`, nav: 'claude' });
  const values = {};
  const holder = h('div');
  const fill = () => String(r.template || '').replace(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g, (whole, name) => (values[name]?.trim() ? values[name].trim() : whole));
  const paint = () => clear(holder).append(promptBlock(fill(), 'prompt', 'Your prompt'));
  const form = h('form.builder', { onsubmit: (event) => event.preventDefault() }, (r.fields || []).map((field) => h('label.builder__field',
    h('span.label', h('b', smart(field.label || field.name))),
    h('textarea', { rows: '2', placeholder: field.placeholder || '', oninput: (event) => { values[field.name] = event.target.value; paint(); } }))));
  paint();
  el.append(h('div.wrap.page', subnav('recipes'),
    folio([h('b', LEVELS[r.level] || r.level), r.minutes_saved ? ` · saves about ${r.minutes_saved} minutes each time` : ''],
      [clipButton(`recipe:${r.id}`, { kind: 'recipe', id: r.id, title: r.title, url: `#/claude/recipe/${r.id}`, source: 'Claude Desk' })]),
    h('div.grid.detail',
      h('div.detail__main',
        (r.prerequisites || []).length ? [h('h2.block__sub.label', h('b', 'Before you start')), h('div.prose', h('ul', r.prerequisites.map((item) => h('li', smart(item)))))] : null,
        h('div.prose', trustedHtml(stripPrompt(r.html))),
        r.template && [h('h2.block__sub.label', h('b', 'Build the prompt')), (r.fields || []).length ? form : null, holder]),
      h('aside.detail__side',
        h('h3.label', h('b', 'Techniques it uses')),
        h('ul.linklist', (r.features || []).map((id) => {
          const feature = book.features.find((f) => f.id === id);
          return feature && h('li', h('a', { href: `#/claude/feature/${id}` }, smart(feature.title), ' ', arw('right')));
        })),
        (r.docs || []).length ? [h('h3.label', h('b', 'Official docs')), h('ul.linklist', r.docs.map((doc) => h('li', outLink(doc.url, {}, smart(doc.title), ' ', arw('ne')))))] : null,
        r.verified && h('p.label', `Checked on ${shortDate(fromDay(r.verified))}`)))));
}

function stripPrompt(html) {
  return String(html || '').replace(/<h2>Prompt<\/h2>\s*<pre>[\s\S]*?<\/pre>/, '');
}

