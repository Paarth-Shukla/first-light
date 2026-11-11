// The quieter pages: Clippings, Back Issues, Settings and the Colophon (how it is made, and source health).

import { h, arw, outLink, clear, append } from '../core/dom.js';
import * as data from '../core/data.js';
import * as store from '../core/store.js';
import * as shell from '../shell.js';
import { desk, smart, folio, notice, filterBar, plural } from '../core/ui.js';
import { clock, shortDate, longDate, fromDay, zoneName, ago } from '../core/time.js';

// ---- Clippings ----------------------------------------------------------------------

const KIND_NAME = { story: 'Stories', paper: 'Papers', feature: 'Claude techniques', recipe: 'Claude recipes' };

function download(name, text, type) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = h('a', { href: url, download: name });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function clippingsMarkdown(items) {
  const lines = ['# Clippings from First Light', ''];
  for (const [kind, name] of Object.entries(KIND_NAME)) {
    const group = items.filter((item) => item.kind === kind);
    if (!group.length) continue;
    lines.push(`## ${name}`, '');
    for (const item of group) {
      const url = String(item.url || '').startsWith('#/') ? '' : item.url;
      lines.push(`- ${url ? `[${item.title}](${url})` : item.title}${item.source ? ` — ${item.source}` : ''} (clipped ${new Date(item.savedAt).toISOString().slice(0, 10)})`);
      if (item.note) lines.push(`  - ${item.note}`);
    }
    lines.push('');
  }
  return lines.join('\n');
}

export async function clippingsView(el, params, ctx) {
  ctx.setPage({ title: 'Clippings', kicker: 'What you kept', nav: 'clippings' });
  const body = h('div');
  const paint = () => {
    const all = Object.entries(store.clippings()).map(([key, item]) => ({ key, ...item })).sort((a, b) => b.savedAt - a.savedAt);
    clear(body);
    if (!all.length) {
      body.append(notice('Nothing clipped yet.', 'Press S on a story, or use the Clip button on any story, paper or Claude technique. Clippings stay in this browser.'));
      return;
    }
    body.append(folio([h('b', 'Clippings'), ` · ${all.length} kept in this browser`], [
      h('button.more', { type: 'button', onclick: () => download('first-light-clippings.md', clippingsMarkdown(all), 'text/markdown') }, h('b', 'Export as Markdown')),
      h('button.more', { type: 'button', onclick: () => download('first-light-clippings.json', JSON.stringify(all, null, 2), 'application/json') }, h('b', 'Export as JSON'))]));
    for (const [kind, name] of Object.entries(KIND_NAME)) {
      const group = all.filter((item) => item.kind === kind);
      if (!group.length) continue;
      body.append(h('section.block', h('header.block__head', h('h2.block__title', name), h('span.label', `${group.length}`)),
        h('ol.rows', group.map((item) => {
          const inApp = String(item.url || '').startsWith('#/');
          const note = h('input.note', { type: 'text', value: item.note || '', placeholder: 'Add a note', 'aria-label': `Note on ${item.title}`, onchange: (event) => store.setNote(item.key, event.target.value.trim()) });
          return h('li.row',
            h('span.row__meta', h('time.row__date', shortDate(item.savedAt)), item.section && h('span.tag.label', desk(item.section).name)),
            h('div.row__main',
              h('p.row__title', inApp ? h('a', { href: item.url, 'data-hl': true }, smart(item.title)) : outLink(item.url, { 'data-hl': true }, smart(item.title))),
              h('p.row__sum', item.source || '', kind === 'story' && item.id ? [' · ', h('a', { href: `#/story/${item.id}${item.day ? `?d=${item.day}` : ''}` }, 'who carried it')] : null),
              note),
            h('p.row__aside.label', h('button.more', { type: 'button', onclick: () => { store.unclip(item.key); paint(); } }, h('b', 'Remove'))));
        }))));
    }
  };
  paint();
  el.append(h('div.wrap.page', body));
}

// ---- Back Issues ------------------------------------------------------------------------

export async function archiveView(el, params, ctx) {
  ctx.setPage({ title: 'Back Issues', kicker: 'Every edition, as it was set' });
  const [index, weekends] = await Promise.all([data.loadOr('editions/index.json', { editions: [] }), data.loadOr('weekend/index.json', { weeks: [] })]);
  const editions = index.editions || [];
  const seen = store.get('seen', {});
  append(el, h('div.wrap.page',
    folio([h('b', 'Back Issues'), ` · ${editions.length} ${plural(editions.length, 'edition')} on file`]),
    editions.length ? h('ol.rows', editions.map((edition) => h('li.row',
      h('span.row__meta', h('span.tile.tile--sm', { 'aria-hidden': 'true' }, String(edition.number)), h('time.row__date', { datetime: edition.date }, shortDate(fromDay(edition.date)))),
      h('div.row__main', h('p.row__title', h('a', { href: `#/edition/${edition.date}`, 'data-hl': true }, smart(edition.headline || `Edition No. ${edition.number}`))),
        h('p.row__sum', longDate(fromDay(edition.date)))),
      h('p.row__aside.label', (seen[edition.date] || []).length ? `${seen[edition.date].length} seen` : 'Unopened'))))
      : notice('No edition has been set yet.', 'Back issues appear here from the first morning the pipeline runs.'),
    (weekends.weeks || []).length ? h('section.block', h('header.block__head', h('h2.block__title', 'Weekend Reviews')),
      h('ol.rows', weekends.weeks.map((week) => h('li.row',
        h('span.row__meta', h('span.tag.label', week.isoWeek), h('time.row__date', shortDate(fromDay(week.to)))),
        h('div.row__main', h('p.row__title', h('a', { href: `#/weekend/${week.isoWeek}`, 'data-hl': true }, smart(week.title || 'Five papers of the week')))),
        h('p.row__aside.label', arw('right')))))) : null));
}

// ---- Settings -----------------------------------------------------------------------------

export async function settingsView(el, params, ctx) {
  ctx.setPage({ title: 'Settings', kicker: 'Kept in this browser only' });
  const prefs = store.get('prefs', {});
  const themeBar = h('div');
  const paintTheme = () => clear(themeBar).append(filterBar(
    [{ id: 'auto', label: 'Follow the system' }, { id: 'light', label: 'Day edition' }, { id: 'dark', label: 'Night edition' }],
    store.get('prefs', {}).theme || prefs.theme || 'auto', (id) => { shell.setTheme(id); paintTheme(); }, { label: 'Theme' }));
  paintTheme();
  const file = h('input', { type: 'file', accept: 'application/json', hidden: true, onchange: async (event) => {
    const chosen = event.target.files[0];
    if (!chosen) return;
    try {
      store.importAll(JSON.parse(await chosen.text()));
      tally.textContent = counts();
      shell.setTheme(store.get('prefs', {}).theme || 'auto'); // an imported theme applies at once, not on the next load
      paintTheme();
      shell.toast('Imported. Reading state, clippings and settings are merged.');
    } catch (error) {
      shell.toast(error.message || 'That file could not be read.');
    }
    event.target.value = '';
  } });
  const counts = () => `${Object.keys(store.get('read', {})).length} stories marked read · ${Object.keys(store.clippings()).length} clippings · ${Object.keys(store.get('claude', {})).length} Claude techniques tracked`;
  const tally = h('p.label', counts());
  el.append(h('div.wrap.page',
    folio([h('b', 'Settings'), ' · nothing here leaves this browser']),
    h('section.block', h('header.block__head', h('h2.block__title', 'Edition')), themeBar,
      h('p.prose', 'N switches between the day and night editions from any page.')),
    h('section.block', h('header.block__head', h('h2.block__title', 'Your state')), tally,
      h('p.prose', 'What you have read, clipped and tried is stored only in this browser. Export it to move to another device or to keep a backup; importing merges with what is already here.'),
      h('p.actions',
        h('button.readon', { type: 'button', onclick: () => download(`first-light-state-${new Date().toISOString().slice(0, 10)}.json`, JSON.stringify(store.exportAll(), null, 2), 'application/json') }, 'Export my state'),
        h('button.readon', { type: 'button', onclick: () => file.click() }, 'Import a state file'), file,
        h('button.readon', { type: 'button', onclick: () => { store.set('read', {}); store.set('seen', {}); tally.textContent = counts(); shell.toast('Reading history cleared.'); } }, 'Clear reading history'),
        h('button.readon.readon--danger', { type: 'button', onclick: (event) => {
          if (event.target.dataset.armed) { store.clearAll(); tally.textContent = counts(); shell.toast('Everything stored in this browser was erased.'); delete event.target.dataset.armed; event.target.textContent = 'Erase everything'; }
          else { event.target.dataset.armed = '1'; event.target.textContent = 'Press again to erase clippings, history and settings'; }
        } }, 'Erase everything'))),
    h('section.block', h('header.block__head', h('h2.block__title', 'What to change in the repository')),
      h('ul.prose',
        h('li', h('code', 'config/sources.json'), ': the feeds each desk reads, with their tier.'),
        h('li', h('code', 'config/markets.json'), ': the indices and the watchlist.'),
        h('li', h('code', 'config/lexicon.json'), ': names, tickers, synonyms and the glossary that search and tagging use.'),
        h('li', h('code', 'config/site.json'), ': timezone, edition hour, ranking weights.'),
        h('li', h('code', 'content/claude/'), ': the Claude Desk playbook and recipes.')))));
}

// ---- Colophon ---------------------------------------------------------------------------------

export async function colophonView(el, params, ctx) {
  ctx.setPage({ title: 'Colophon', kicker: 'How it is made, and how the last build went' });
  const [manifest, status] = await Promise.all([data.manifest(), data.loadOr('status.json', null)]);
  const sources = status?.sources || [];
  const failed = sources.filter((source) => !source.ok);
  let only = 'failed';
  const table = h('div');
  const paintTable = () => {
    const shown = only === 'failed' ? failed : sources;
    clear(table).append(
      filterBar([{ id: 'failed', label: 'Failing', count: failed.length }, { id: 'all', label: 'All sources', count: sources.length }], only, (id) => { only = id; paintTable(); }, { label: 'Sources' }),
      shown.length ? h('div.tablewrap', h('table.mkt.health',
        h('thead', h('tr.label', ['Source', 'Desk', 'Items', 'New', 'Time', 'State'].map((name) => h('th', { scope: 'col' }, name)))),
        h('tbody', shown.map((source) => h('tr',
          h('td', h('span.mkt__name', h('b', source.name || source.id))),
          h('td.data', desk(source.section).name),
          h('td.data', String(source.items ?? '–')),
          h('td.data', String(source.newItems ?? '–')),
          h('td.data', source.ms ? `${(source.ms / 1000).toFixed(1)} s` : '–'),
          h('td.data', source.ok ? 'OK' : h('span.is-stale', { title: source.error || '' }, smart(String(source.error || 'Failed').slice(0, 60))))))))) : h('p.block__empty', only === 'failed' ? 'Every source answered on the last build.' : 'No source report yet.'));
  };
  paintTable();
  append(el, h('div.wrap.page',
    folio([h('b', 'Colophon'), ` · built ${shortDate(manifest.builtAt)} ${clock(manifest.builtAt)} ${zoneName()} (${ago(manifest.builtAt)})`]),
    h('div.grid.detail',
      h('div.detail__main.prose',
        h('h2', 'What this is'),
        h('p', 'First Light is a personal daily newspaper. A small program reads a few hundred public feeds, groups the reports of one event from different outlets into one story, and ranks stories mostly by how many outlets carried them. Once a morning it freezes a finite edition. The Wire behind it keeps moving.'),
        h('h2', 'What it does not do'),
        h('p', 'It does not copy articles: only the headline, a line of summary and the link. It does not write anything itself: summaries are the outlets’ own words, and the paper digests in the Weekend Review are sentences lifted from each abstract. It does not track you: there is no account and no analytics, and what you read stays in this browser.'),
        h('h2', 'How a story earns its size'),
        h('p', 'Breadth of coverage counts most, then the standing of the outlets, how recent the story is, how fast it spread, discussion elsewhere, and where curated front pages placed it. Every story’s page shows these numbers. The weights are a file in the repository.'),
        h('h2', 'Type'),
        h('p', 'Archivo for text and headlines, Martian Mono for figures; both open licence and served from this site.')),
      h('aside.detail__side',
        h('h3.label', h('b', 'This build')),
        h('table.quotes.data', h('tbody',
          [['Stories on file', manifest.counts?.stories], ['Sources answering', manifest.counts ? `${manifest.counts.sourcesOk} of ${manifest.counts.sources}` : null],
            ['Editions', (manifest.editions || []).length], ['Days on the wire', (manifest.days || []).length], ['Weekend Reviews', (manifest.weekends || []).length]]
            .filter(([, value]) => value !== null && value !== undefined).map(([name, value]) => h('tr', h('th', { scope: 'row' }, name), h('td', String(value)))))),
        (status?.stages || []).length ? [h('h3.label', h('b', 'Stages')),
          h('table.quotes.data', h('tbody', status.stages.map((stage) => h('tr', h('th', { scope: 'row' }, stage.stage),
            h('td', stage.ok ? `${Number(stage.durationSec || 0).toFixed(1)} s` : h('span.is-stale', { title: stage.error || '' }, 'failed'))))))] : null)),
    h('section.block', h('header.block__head', h('h2.block__title', 'Source health'), h('span.label', sources.length ? `${sources.length - failed.length} of ${sources.length} answered` : '')), table)));
}
