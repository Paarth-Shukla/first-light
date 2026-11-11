// Search every edition. The query is widened with names, synonyms and terms the news itself links,
// and the widening is shown as chips the reader can drop, so nothing is searched behind their back.

import { h, arw, outLink, clear, append } from '../core/dom.js';
import * as data from '../core/data.js';
import * as store from '../core/store.js';
import * as shell from '../shell.js';
import { desk, smart, folio, filterBar, plural, chg, fmtNumber, notice } from '../core/ui.js';
import { shortDate, localDate } from '../core/time.js';
import { replaceQuery } from '../core/router.js';
import { highlight, stem, tokenize } from '../search/engine.js';
import * as client from '../search/client.js';

const KINDS = [
  { id: 'all', label: 'Everything', kinds: null },
  { id: 'story', label: 'Stories', kinds: ['story'] },
  { id: 'paper', label: 'Papers', kinds: ['paper'] },
  { id: 'claude', label: 'Claude Desk', kinds: ['update', 'feature', 'recipe'] },
  { id: 'term', label: 'Glossary', kinds: ['term'] },
];
const KIND_LABEL = { story: 'Story', paper: 'Paper', update: 'Claude update', feature: 'Technique', recipe: 'Recipe', term: 'Glossary' };
const VIA = { alias: 'also known as', entity: 'name', relatedEntity: 'related name', related: 'often in the same stories', prefix: 'starts with', fuzzy: 'close spelling' };

function marked(text, marks) {
  return highlight(smart(text), marks).map((piece) => (piece.mark ? h('mark', piece.text) : piece.text));
}

function hitRow(hit, marks) {
  const doc = hit.doc;
  const inApp = String(doc.u || '').startsWith('#/');
  const where = doc.k === 'story' ? `${doc.d ? shortDate(doc.d) : ''} · ${desk(doc.c).name}` : `${doc.d ? `${shortDate(doc.d)} · ` : ''}${KIND_LABEL[doc.k] || doc.k}`;
  const title = inApp
    ? h('a.story__hl.hl-2', { href: doc.u, 'data-hl': true }, marked(doc.t, marks))
    : outLink(doc.u, { class: 'story__hl hl-2', 'data-hl': true, onclick: () => { if (doc.k === 'story') store.markRead(doc.i); } }, marked(doc.t, marks));
  return h(`li.hit${doc.k === 'story' && store.isRead(doc.i) ? '.is-read' : ''}`, { dataset: { story: doc.i } },
    h('span.label', where),
    h('div.hit__main', title,
      doc.s && h('p.hit__sum', marked(doc.s, marks)),
      hit.via?.length ? h('p.hit__via.label', `Found through ${[...new Set(hit.via)].slice(0, 3).join(', ')}`) : null),
    h('span.label', h('b', doc.o || ''), doc.k === 'story' && doc.n > 1 ? [' · ', h('a', { href: `#/story/${doc.i}?d=${localDate(doc.d)}`, title: 'See who carried it' }, `${doc.n} ${plural(doc.n, 'outlet')}`)] : null));
}

export async function searchView(el, params, ctx) {
  ctx.setPage({ title: 'Search', kicker: 'Every edition on file' });
  const state = { q: params.query.q || '', kind: params.query.in || 'all', sort: params.query.sort === 'newest' ? 'newest' : 'relevance', exact: false, drop: new Set(), dropLabels: new Set(), limit: 40 };
  let run = 0;
  let timer = null;
  let lastResult = null;
  let shownDocs = 0; // how much of the archive was loaded when the results on screen were computed

  const input = h('input#q2', { type: 'search', value: state.q, autocomplete: 'off', spellcheck: 'false', placeholder: 'A name, a topic, a ticker', 'data-find': true, 'aria-describedby': 'find-count' });
  const count = h('span.find__count.label#find-count');
  const also = h('div');
  const tabs = h('div');
  const cards = h('div');
  const list = h('ol.hits');
  const foot = h('div.hits__foot');
  const svg = arw('find');
  svg.setAttribute('class', 'search__glyph');

  const recent = () => store.get('search', {}).recent || [];
  const remember = (query) => {
    const text = query.trim();
    if (text.length < 2) return;
    store.update('search', {}, (s) => ({ ...s, recent: [text, ...(s.recent || []).filter((item) => item.toLowerCase() !== text.toLowerCase())].slice(0, 12) }));
  };

  const paintIdle = async () => {
    clear(also); clear(tabs); clear(cards); clear(list);
    count.textContent = '';
    const hot = await data.loadOr('latest.json', { trending: [] });
    const set = (query) => { input.value = query; state.q = query; state.drop.clear(); state.dropLabels.clear(); go(); input.focus(); };
    append(clear(foot),
      recent().length ? h('section.block', h('header.block__head', h('h2.block__title', 'Recent searches'),
        h('button.more.label', { type: 'button', onclick: () => { store.update('search', {}, (s) => ({ ...s, recent: [] })); paintIdle(); } }, h('b', 'Forget them'))),
      h('p.taglist', recent().map((query) => h('button.chip', { type: 'button', onclick: () => set(query) }, query)))) : null,
      hot.trending?.length ? h('section.block', h('header.block__head', h('h2.block__title', 'Rising today')),
        h('p.taglist', hot.trending.slice(0, 12).map((t) => h('button.chip', { type: 'button', onclick: () => set(t.name) }, t.name)))) : null,
      h('section.block', h('header.block__head', h('h2.block__title', 'How to ask')),
        h('ul.prose.ops',
          h('li', h('code', 'nvidia'), ' also finds NVDA, Jensen Huang and the terms the news links to it. Each widening shows as a chip you can drop.'),
          h('li', h('code', '"rate cut"'), ' finds the exact phrase. ', h('code', '-crypto'), ' leaves a word out.'),
          h('li', h('code', 'desk:ai'), ', ', h('code', 'source:reuters'), ', ', h('code', 'in:papers'), ', ', h('code', 'in:claude'), ', ', h('code', 'after:2026-11-01'), ', ', h('code', 'is:saved'), ', ', h('code', 'is:unread'), ' narrow the search.'))));
  };

  const paint = (result, engineState) => {
    lastResult = result;
    clear(cards); clear(list); clear(foot);
    const marks = new Set(result.marks);
    for (const token of tokenize(state.q)) marks.add(stem(token));
    count.replaceChildren(h('b', `${result.total} ${plural(result.total, 'result')}`), engineState.pending?.length ? ` · reading ${engineState.pending.length} older ${plural(engineState.pending.length, 'month')}` : ` · ${engineState.docs.toLocaleString('en-IN')} items on file`);

    // the widening, shown
    clear(also);
    // one chip per label: a name can arrive both as a related name and as a co-occurring term
    const byLabel = new Map();
    for (const x of result.expansions.filter((item) => item.count > 0)) {
      const same = byLabel.get(x.label.toLowerCase());
      if (same) { same.keys.push(x.key); same.count = Math.max(same.count, x.count); } else byLabel.set(x.label.toLowerCase(), { ...x, keys: [x.key] });
    }
    const shown = [...byLabel.values()].slice(0, 14);
    if (shown.length || state.drop.size || state.exact) {
      also.append(h('p.also', h('span.label', state.exact ? 'Exact words only' : 'Also searching'),
        !state.exact && shown.map((x) => h('button.chip', { type: 'button', title: `${VIA[x.kind] || 'related'} “${x.from}” · ${x.count} ${x.count === 1 ? 'match' : 'matches'}. Click to drop it.`, 'aria-label': `Stop searching ${x.label}`,
          onclick: () => { for (const key of x.keys) state.drop.add(key); state.dropLabels.add(x.label.toLowerCase()); go(); } }, x.label, h('span.x', { 'aria-hidden': 'true' }, '×'))),
        state.drop.size ? h('button.more.label', { type: 'button', onclick: () => { state.drop.clear(); state.dropLabels.clear(); go(); } }, h('b', `Restore ${state.dropLabels.size || state.drop.size} dropped`)) : null,
        h('button.more.label', { type: 'button', 'aria-pressed': String(state.exact), onclick: () => { state.exact = !state.exact; go(); } }, h('b', state.exact ? 'Widen the search again' : 'Exact words only'))));
    }

    clear(tabs).append(h('div.findbar',
      filterBar(KINDS.map((k) => ({ id: k.id, label: k.label })), state.kind, (id) => { state.kind = id; state.limit = 40; sync(); go(); }, { label: 'Kind' }),
      filterBar([{ id: 'relevance', label: 'Most relevant' }, { id: 'newest', label: 'Newest' }], state.sort, (id) => { state.sort = id; sync(); go(); }, { label: 'Order' })));

    if (result.definition) cards.append(h('aside.defcard', h('span.label', h('b', 'Glossary')), h('p.defcard__term', result.definition.term), h('p', smart(result.definition.definition))));
    if (result.entity) paintEntity(result.entity);
    if (result.partial) cards.append(h('p.label.is-quiet', 'Nothing matches every word, so these match some of them.'));
    if (result.didYouMean) cards.append(h('p.didyou', 'Did you mean ', h('button.more', { type: 'button', onclick: () => { input.value = result.didYouMean; state.q = result.didYouMean; go(); } }, h('b', result.didYouMean)), '?'));

    if (!result.total) {
      foot.append(notice(`Nothing on file for “${state.q}”.`,
        engineState.pending?.length ? 'Older months are still loading; results will appear here if they hold a match.' : 'Try fewer words, or drop a filter. The archive holds 90 days of stories.'));
      return;
    }
    list.append(...result.hits.map((hit) => hitRow(hit, marks)));
    if (result.total > result.hits.length) foot.append(h('button.readon', { type: 'button', onclick: () => { state.limit += 40; go(); } }, `Show ${Math.min(40, result.total - result.hits.length)} more`));
  };

  const paintEntity = async (entity) => {
    const holder = h('aside.defcard');
    cards.append(holder);
    const marketsData = entity.ticker ? await data.markets() : null;
    const quote = marketsData?.groups?.flatMap((group) => group.quotes).find((q) => q.symbol === entity.ticker);
    append(holder, h('span.label', h('b', entity.type || 'Name')), h('p.defcard__term', entity.name),
      quote ? h('p.data', `${fmtNumber(quote.price)} `, chg(quote.changePct), ' ', h('a.more.label', { href: '#/markets' }, h('b', 'Markets'), arw('right'))) : null,
      (entity.related || []).length ? h('p.label', 'Related: ', entity.related.slice(0, 6).map((id, index) => [index ? ' · ' : '', h('a', { href: `#/search?q=${encodeURIComponent(id.replace(/-/g, ' '))}` }, id.replace(/-/g, ' '))])) : null);
  };

  const sync = () => replaceQuery({ q: state.q || null, in: state.kind === 'all' ? null : state.kind, sort: state.sort === 'newest' ? 'newest' : null });

  const go = async () => {
    sync();
    const query = state.q.trim();
    const mine = ++run; // also retires any search still in flight when the box is cleared
    if (!query) { paintIdle(); return; }
    const result = await client.search(query, { limit: state.limit, sort: state.sort, exactOnly: state.exact, drop: [...state.drop], typing: document.activeElement === input,
      kinds: KINDS.find((k) => k.id === state.kind)?.kinds || undefined });
    if (mine !== run) return; // a newer keystroke has already asked again
    // an index that never loaded is not an empty result: say so instead of "Nothing on file"
    if (!result || (client.state().error && !client.state().docs)) { clear(list); clear(cards); clear(also); count.textContent = ''; clear(foot).append(notice('Search could not start.', 'The search index did not load. It is built by the pipeline’s search stage; run the pipeline, then reload.')); return; }
    shownDocs = client.state().docs;
    paint(result, client.state());
  };

  input.addEventListener('input', () => {
    state.q = input.value;
    state.limit = 40;
    clearTimeout(timer);
    timer = setTimeout(go, 90);
  });
  const form = h('form.find', { role: 'search', onsubmit: (event) => { event.preventDefault(); clearTimeout(timer); remember(state.q); go(); } },
    svg, h('label.vh', { for: 'q2' }, 'Search every edition'), input, count, h('kbd', { 'aria-hidden': 'true' }, '/'));

  el.append(h('div.wrap.page',
    folio([h('b', 'Search'), ' · stories, papers, Claude Desk and the glossary']),
    form, also, tabs, cards, list, foot));

  const stopState = client.onState((engineState) => {
    // when another month of the archive lands, ask again so older matches appear
    if (engineState.ready && state.q.trim() && lastResult && engineState.docs !== shownDocs) go();
  });
  await go();
  if (!params.query.q) input.focus();
  return () => {
    clearTimeout(timer);
    stopState();
    if (lastResult?.total) remember(state.q);
  };
}
