// The Wire (everything, live, one line each) and the desk pages (one section: its top stories, then its wire).

import { h, arw, outLink, clear, append } from '../core/dom.js';
import * as data from '../core/data.js';
import * as store from '../core/store.js';
import * as shell from '../shell.js';
import { allDesks, desk, ticks, headline, plural, folio, notice, filterBar, storyCard, storyHref, storyKey, storySnapshot, clipButton, tier, RAIL_STEP, RAIL_SPAN } from '../core/ui.js';
import { clock, localDate, shortDate, fromDay, weekday, zoneName, hoursSince } from '../core/time.js';
import { replaceQuery } from '../core/router.js';

const PAGE = 150;

function wireRow(story, today) {
  const n = story.sourceCount || 1;
  const d = desk(story.section);
  const at = story.updatedAt || story.publishedAt;
  const sameDay = localDate(at) === today;
  const weight = n >= 6 ? '.wire__hl--3' : n <= 2 ? '.wire__hl--1' : '';
  const row = h(`li.wire__row${store.isRead(story.id) ? '.is-read' : ''}`, { dataset: { story: story.id } },
    h('span.unread', { title: 'Unread' }),
    h('time.wire__time', { datetime: at, title: `${shortDate(at)} ${clock(at)} ${zoneName()}` }, sameDay ? clock(at) : weekday(at)),
    h('a.wire__desk', { href: `#/s/${story.section}`, tabindex: '-1' }, h('span.tile.tile--sm', { 'aria-hidden': 'true' }, d.no), h('span.label', d.name)),
    outLink(story.url, { class: `wire__hl ${weight.slice(1)}`.trim(), 'data-hl': true, onclick: () => { store.markRead(story.id); row.classList.add('is-read'); } }, headline(story.title)),
    h('a.cov.label', { href: storyHref(story), title: `${n} ${plural(n, 'outlet')}: see who carried it`, tabindex: '-1' }, ticks(n), h('b', String(n))),
    h('span.wire__src.label', story.sources?.[0]?.name || ''),
    clipButton(storyKey(story), storySnapshot(story), { label: 'Clip', done: 'Clipped' }));
  row.addEventListener('focusin', () => row.classList.add('is-cursor'));
  row.addEventListener('focusout', () => row.classList.remove('is-cursor'));
  return row;
}

/**
 * The live list with its filter bar. `fixedDesk` pins the desk (desk pages); otherwise the reader picks.
 * Returns {element, cleanup}.
 */
function wireList({ stories, manifest, query, ctx, fixedDesk = null, entityFilter = null }) {
  const today = localDate(Date.now());
  const seenAt = store.get('visit', {}).wireSeenAt || 0;
  const state = {
    desk: fixedDesk || query.desk || 'all',
    cov: Number(query.cov) || 1,
    unread: query.unread === '1',
    sort: query.sort === 'ranked' ? 'ranked' : 'latest',
    entity: entityFilter,
    shown: PAGE,
  };
  const pool = new Map(stories.map((story) => [story.id, story]));
  const loadedDays = new Set();
  const olderDays = [...(manifest.days || [])].sort().reverse();

  const bar = h('div.wire__controls');
  const list = h('ol');
  const more = h('p.wire__more');
  const head = h('div.wire__row.wire__row--head.label', { 'aria-hidden': 'true' }, h('span'), h('span', 'Time'), h('span', 'Desk'), h('span', 'Headline'), h('span', 'Outlets'), h('span', { style: 'text-align:right' }, 'Source'), h('span'));
  const live = h('span.live');

  const filtered = () => {
    let rows = [...pool.values()];
    if (state.desk !== 'all') rows = rows.filter((story) => story.section === state.desk || (story.sections || []).includes(state.desk));
    if (state.cov > 1) rows = rows.filter((story) => (story.sourceCount || 1) >= state.cov);
    if (state.unread) rows = rows.filter((story) => !store.isRead(story.id));
    if (state.entity) rows = rows.filter((story) => (story.entities || []).includes(state.entity));
    const time = (story) => Date.parse(story.updatedAt || story.publishedAt);
    rows.sort(state.sort === 'ranked' ? (a, b) => b.score - a.score || time(b) - time(a) : (a, b) => time(b) - time(a));
    return rows;
  };

  const sync = () => { if (!fixedDesk) replaceQuery({ desk: state.desk === 'all' ? null : state.desk, cov: state.cov > 1 ? state.cov : null, unread: state.unread ? 1 : null, sort: state.sort === 'ranked' ? 'ranked' : null }); };

  const paintRows = () => {
    const rows = filtered();
    const fresh = rows.filter((story) => Date.parse(story.updatedAt || story.publishedAt) > seenAt).length;
    clear(live).append(h('span.unread', { 'aria-hidden': 'true' }), `${rows.length} ${plural(rows.length, 'story').replace('storys', 'stories')}`, seenAt && fresh ? ` · ${fresh} new since your last look` : '');
    clear(list);
    let lastDay = null;
    let dividerDone = !seenAt || state.sort !== 'latest';
    for (const story of rows.slice(0, state.shown)) {
      const at = story.updatedAt || story.publishedAt;
      if (!dividerDone && Date.parse(at) <= seenAt) {
        dividerDone = true;
        if (list.children.length) list.append(h('li.wire__mark.label', h('b', 'Seen on your last look'), ' · everything below was already here'));
      }
      const dayOf = localDate(at);
      if (state.sort === 'latest' && dayOf !== lastDay) {
        if (lastDay !== null || dayOf !== today) list.append(h('li.wire__day.label', h('b', shortDate(fromDay(dayOf)))));
        lastDay = dayOf;
      }
      list.append(wireRow(story, today));
    }
    clear(more);
    if (!rows.length) {
      more.append(notice('Nothing on the wire matches.', state.unread ? 'You have read everything here.' : 'Try another desk or a lower coverage bar.'));
    } else if (rows.length > state.shown) {
      more.append(h('button.readon', { type: 'button', onclick: () => { state.shown += PAGE; paintRows(); } }, `Show ${Math.min(PAGE, rows.length - state.shown)} more`));
    }
    const nextDay = olderDays.find((day) => !loadedDays.has(day) && day < oldestDay());
    if (nextDay) {
      more.append(h('button.readon', { type: 'button', onclick: async (event) => {
        event.target.disabled = true;
        const file = await data.loadOr(`stories/${nextDay}.json`, { stories: [] });
        loadedDays.add(nextDay);
        for (const story of file.stories) if (!pool.has(story.id)) pool.set(story.id, story);
        state.shown += PAGE;
        paintRows();
      } }, `Load ${shortDate(fromDay(nextDay))}`));
    }
  };

  const oldestDay = () => {
    let oldest = today;
    for (const story of pool.values()) if (story.day && story.day < oldest) oldest = story.day;
    return oldest;
  };

  const paint = () => {
    clear(bar);
    if (!fixedDesk) {
      bar.append(filterBar([{ id: 'all', label: 'All desks' }, ...allDesks().map((d) => ({ id: d.id, label: `${d.no} ${d.name}` }))], state.desk,
        (id) => { state.desk = id; state.shown = PAGE; sync(); paint(); }, { label: 'Desk' }));
    }
    bar.append(h('div.wire__toggles',
      filterBar([{ id: 1, label: 'Any coverage' }, { id: 3, label: '3+ outlets' }, { id: 6, label: '6+ outlets' }], state.cov,
        (id) => { state.cov = id; state.shown = PAGE; sync(); paint(); }, { label: 'Coverage' }),
      filterBar([{ id: 'latest', label: 'Latest' }, { id: 'ranked', label: 'Ranked' }], state.sort,
        (id) => { state.sort = id; sync(); paint(); }, { label: 'Order' }),
      h('button.chip', { type: 'button', class: state.unread ? 'chip--solid' : '', 'aria-pressed': String(state.unread),
        onclick: () => { state.unread = !state.unread; state.shown = PAGE; sync(); paint(); } }, 'Unread only ', h('kbd', 'U'))));
    paintRows();
  };
  paint();

  const element = h('div.wire',
    h('div.wire__bar.label', live, h('span.push', h('span', `Built ${clock(manifest.builtAt)} ${zoneName()}`))),
    bar, head, list, more,
    h('p.wire__keys.label', h('span', h('kbd', 'J'), h('kbd', 'K'), ' move'), h('span', h('kbd', 'O'), ' open at source'), h('span', h('kbd', 'S'), ' clip'),
      h('span', h('kbd', 'X'), ' mark read'), !fixedDesk && h('span', h('kbd', '1'), '–', h('kbd', '0'), ' filter to a desk'), h('span', h('kbd', '/'), ' search')));

  const keys = { u: () => { state.unread = !state.unread; state.shown = PAGE; sync(); paint(); } };
  if (!fixedDesk) {
    allDesks().forEach((d, index) => { keys[String((index + 1) % 10)] = () => { state.desk = state.desk === d.id ? 'all' : d.id; state.shown = PAGE; sync(); paint(); }; });
    keys.a = () => { state.desk = 'all'; sync(); paint(); };
  }
  ctx.setViewKeys(keys);
  return { element, setEntity: (id) => { state.entity = id; state.shown = PAGE; paintRows(); } };
}

export async function wireView(el, params, ctx) {
  ctx.setPage({ title: 'The Wire', kicker: 'Everything, as it arrives', nav: 'wire' });
  const [manifest, hot] = await Promise.all([data.manifest(), data.loadOr('latest.json', null)]);
  if (!hot?.stories?.length) {
    el.append(h('div.wrap.page', notice('The wire is silent.', 'No stories have been fetched yet. Run the pipeline, or wait for the next scheduled build.')));
    return undefined;
  }
  const stale = hoursSince(hot.generatedAt) > 26;
  const { element } = wireList({ stories: hot.stories, manifest, query: params.query, ctx });
  append(el, h('div.wrap.page',
    folio([h('b', 'The Wire'), ` · the last 48 hours across ${allDesks().length} desks`], stale && [h('span.is-stale', `Last built ${shortDate(hot.generatedAt)} ${clock(hot.generatedAt)}: the feed may be behind`)]),
    hot.trending?.length ? h('p.trending.label', h('b', 'Rising'), hot.trending.slice(0, 8).map((t) => h('a.chip', { href: `#/search?q=${encodeURIComponent(t.name)}`, title: `${t.count} stories today, ${t.ratio.toFixed(1)}× its usual` }, t.name))) : null,
    element));
  // Record the look when the reader leaves the Wire, including by closing or reloading the tab.
  const markSeen = () => { if (ctx.shown) store.update('visit', {}, (visit) => ({ ...visit, wireSeenAt: Date.now() })); };
  window.addEventListener('pagehide', markSeen);
  return () => {
    window.removeEventListener('pagehide', markSeen);
    if (!ctx.shown) return; // the reader left before the Wire was on screen: they have not seen it
    markSeen();
    shell.refreshWireCount();
  };
}

export async function deskView(el, params, ctx) {
  const d = desk(params.section);
  const [manifest, hot] = await Promise.all([data.manifest(), data.loadOr('latest.json', { stories: [] })]);
  if (!allDesks().some((item) => item.id === params.section)) {
    ctx.setPage({ title: 'No such desk', kicker: 'Desks' });
    el.append(h('div.wrap.page', notice('There is no desk by that name.', null, h('a.readon', { href: '#/wire' }, 'Open The Wire ', arw('right')))));
    return undefined;
  }
  ctx.setPage({ title: d.name, kicker: `Desk ${d.no}`, desk: d.id });
  const stories = hot.stories.filter((story) => story.section === d.id || (story.sections || []).includes(d.id));
  if (!stories.length) {
    el.append(h('div.wrap.page', notice(`Nothing on the ${d.name} desk in the last 48 hours.`, 'Older days are in Back Issues and in search.', h('a.readon', { href: '#/wire' }, 'Open The Wire ', arw('right')))));
    return undefined;
  }
  const today = localDate(Date.now());
  const top = [...stories].filter((story) => story.section === d.id).sort((a, b) => b.score - a.score).slice(0, 3);
  const counts = new Map();
  for (const story of stories) for (const id of story.entities || []) counts.set(id, (counts.get(id) || 0) + 1);
  const lexicon = await data.loadOr('search/lexicon.json', { entities: {} });
  const names = [...counts.entries()].filter(([, n]) => n >= 2).sort((a, b) => b[1] - a[1]).slice(0, 12)
    .map(([id, n]) => ({ id, label: lexicon.entities?.[id]?.name || id, count: n }));
  let entity = null;
  const chips = h('div');
  const { element, setEntity } = wireList({ stories, manifest, query: params.query, ctx, fixedDesk: d.id });
  const paintChips = () => {
    clear(chips);
    if (names.length) chips.append(filterBar([{ id: null, label: 'Everything' }, ...names], entity, (id) => { entity = id; setEntity(id); paintChips(); }, { label: 'Filter by name' }));
  };
  paintChips();
  append(el, h('div.wrap.page',
    folio([h('b', d.name), ` · ${stories.length} ${plural(stories.length, 'story').replace('storys', 'stories')} in the last 48 hours`]),
    top.length ? h('div.grid.deskrow', h('section.desk.desk--12', { 'aria-label': 'Top of the desk' },
      h('header.desk__head', h('span.tile', { 'aria-hidden': 'true' }, d.no), h('h2.desk__name', 'Top of the desk')),
      h('div.desk__body', top.map((story) => storyCard(story, { step: RAIL_STEP[tier(story.sourceCount)], cls: RAIL_SPAN[tier(story.sourceCount)], day: today }))))) : null,
    h('header.block__head', h('h2.block__title', 'The desk’s wire')),
    chips, element));
  return undefined;
}
