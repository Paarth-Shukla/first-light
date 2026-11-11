// The Front Page: one frozen, finite edition, typeset from editions/<date>.json.

import { h, arw, outLink } from '../core/dom.js';
import * as data from '../core/data.js';
import * as store from '../core/store.js';
import * as shell from '../shell.js';
import {
  storyCard, covFoot, ticks, headline, sentences, smart, desk, tier, plural, chg, spark, fmtNumber, folio, notice,
  FRONT_STEP, DESK_STEP, WIDE_STEP, RAIL_STEP, RAIL_SPAN, storyHref, storyKey, storySnapshot, clipButton,
} from '../core/ui.js';
import { clock, stamp, longDate, shortDate, fromDay, zoneName, weekday } from '../core/time.js';
import { adoptControl, promptBlock, whenLine } from './claude.js';

/** Every story in an edition, in reading order. */
export function editionStories(edition) {
  return [edition.lead, ...(edition.front || []), ...(edition.briefs || []), ...(edition.sections || []).flatMap((section) => section.stories)].filter(Boolean);
}

function leadBlock(story, day) {
  const n = story.sourceCount || 1;
  const d = desk(story.section);
  const parts = sentences(story.summary).filter((part) => /[.!?]["”’]?$/.test(part));
  const why = (story.why || []).join(' · ');
  const deck = parts.length > 1 ? smart(parts[0]) : (parts.length ? smart(parts[0]) : '');
  const body = parts.length > 1 ? smart(parts.slice(1, 3).join(' ')) : '';
  const source = story.sources?.[0]?.name || '';
  const link = outLink(story.url, { 'data-hl': true, onclick: () => store.markRead(story.id) }, headline(story.title));
  return h('article.lead', { dataset: { outlets: String(n), story: story.id } },
    h('p.lead__kicker.label', h('span.flag', 'The lead'), h('span', h('b', d.no), ` ${d.name}`),
      h('span.push', h('b', source), ' · ', h('time', { datetime: story.publishedAt }, stamp(story.updatedAt || story.publishedAt, day)))),
    h(`h2.lead__hl${story.title.length > 100 ? '.lead__hl--long' : ''}`, link),
    h('div.lead__foot',
      h(`a.cov-xl${n >= 10 ? '.cov-xl--wide' : ''}`, { href: storyHref(story), title: `Carried by ${n} ${plural(n, 'outlet')}: see who` },
        h('span.cov-xl__n', String(n)),
        h('span.cov-xl__what', ticks(n), h('span.label', plural(n, 'outlet'), h('br'), 'carried', h('br'), 'this')),
        h('p.cov-xl__who.label', n > 1 ? `${source} + ${n - 1} ${plural(n - 1, 'other')}` : source)),
      deck && h('p.lead__deck', deck),
      h('div.lead__body',
        body && h('p', body),
        why && h('p.lead__why.label', h('b', 'Why it leads'), ` · ${why}`),
        h('p.lead__acts', outLink(story.url, { class: 'readon', onclick: () => store.markRead(story.id) }, `Read at ${source} `, arw('ne')),
          clipButton(storyKey(story), storySnapshot(story))))));
}

function seconds(front, day) {
  if (!front.length) return null;
  const [a, b, c, d] = front;
  const row = (wide, narrow, first) => h('div.seconds__row',
    h('div.seconds__wide', storyCard(wide, { step: first ? 'hl-6' : FRONT_STEP[tier(wide.sourceCount)], cov: first ? 'l' : 's', deskTag: true, day })),
    narrow && h('div.seconds__narrow', storyCard(narrow, { step: FRONT_STEP[tier(narrow.sourceCount)], cov: first ? 'l' : 's', deskTag: true, day })));
  return h('div.seconds', row(a, b, true), c && row(c, d, false));
}

function briefs(list, edition, wireNew) {
  const day = edition.date;
  const items = [...list].sort((x, y) => Date.parse(y.updatedAt || y.publishedAt) - Date.parse(x.updatedAt || x.publishedAt));
  return h('aside.briefs.board', { 'aria-labelledby': 'brief-h' },
    h('div.briefs__head', h('h2.briefs__title#brief-h', 'In brief'), h('span.label', `${items.length} ${plural(items.length, 'line')}`)),
    h('ol.briefs__list', items.map((story) => {
      const at = story.updatedAt || story.publishedAt;
      const sameDay = stamp(at, day) === clock(at);
      const n = story.sourceCount || 1;
      return h('li.brief', { dataset: { story: story.id } },
        h('span.brief__time', clock(at), !sameDay && h('small', weekday(at))),
        h('p.brief__hl', outLink(story.url, { 'data-hl': true, onclick: () => store.markRead(story.id) }, headline(story.title))),
        h('p.brief__meta.label', { title: `${n} ${plural(n, 'outlet')}` }, ticks(n), h('span.vh', `${n} ${plural(n, 'outlet')} · `),
          h('span', `${desk(story.section).name} · ${story.sources?.[0]?.name || ''}`)));
    })),
    h('div.briefs__wire', h('p.label', 'Since this edition closed'),
      h('a', { href: '#/wire' }, h('span', wireNew ? `The Wire · ${wireNew} new` : 'The Wire'), arw('right'))));
}

function deskHead(section) {
  const d = desk(section.id);
  return h('header.desk__head', h('span.tile', { 'aria-hidden': 'true' }, d.no), h('h2.desk__name', { id: `desk-${d.no}` }, d.name),
    h('a.desk__more.label.more', { href: `#/s/${section.id}`, 'aria-label': `Everything on the ${d.name} desk` }, h('b', 'All'), arw('right')));
}

function deskNarrow(section, day) {
  return h('section.desk.desk--3', { 'aria-labelledby': `desk-${desk(section.id).no}` }, deskHead(section),
    h('div.desk__body', section.stories.map((story, index) => storyCard(story, { step: DESK_STEP[tier(story.sourceCount)], clamp: index ? 3 : null, day }))));
}

function deskWide(section, day, flip) {
  const [first, ...rest] = section.stories;
  return h(`section.desk.desk--6${flip ? '.desk--flip' : ''}`, { 'aria-labelledby': `desk-${desk(section.id).no}` }, deskHead(section),
    h('div.desk__body',
      h('div.desk__first', storyCard(first, { step: WIDE_STEP[tier(first.sourceCount)], cov: 'foot', day }), covFoot(first)),
      h('div.desk__stack', rest.map((story) => storyCard(story, { step: DESK_STEP[tier(story.sourceCount)], clamp: 3, day })))));
}

function deskRail(section, day) {
  return h('section.desk.desk--12', { 'aria-labelledby': `desk-${desk(section.id).no}` }, deskHead(section),
    h('div.desk__body', section.stories.map((story) => storyCard(story, { step: RAIL_STEP[tier(story.sourceCount)], cls: RAIL_SPAN[tier(story.sourceCount)], day }))));
}

/**
 * Lay the desks out in rows of twelve columns: a wide desk (6) with two narrow ones (3 + 3),
 * the wide one alternating sides; two left over share a row; one left over runs as a rail.
 */
function deskRows(sections, day) {
  const rows = [];
  const filled = sections.filter((section) => section.stories?.length);
  for (let i = 0, rowNo = 0; i < filled.length; rowNo++) {
    const left = filled.length - i;
    if (left >= 3) {
      const trio = filled.slice(i, i + 3);
      const flip = rowNo % 2 === 1;
      const wideAt = flip ? 2 : 0;
      rows.push(h('div.grid.deskrow', trio.map((section, index) => (index === wideAt && section.stories.length > 1 ? deskWide(section, day, flip) : (index === wideAt ? deskRailAsWide(section, day) : deskNarrow(section, day))))));
      i += 3;
    } else if (left === 2) {
      rows.push(h('div.grid.deskrow', deskWide(filled[i], day, false), deskWide(filled[i + 1], day, true)));
      i += 2;
    } else {
      rows.push(h('div.grid.deskrow', deskRail(filled[i], day)));
      i += 1;
    }
  }
  return rows;
}

/** A desk with a single story still has to fill its six columns. */
function deskRailAsWide(section, day) {
  const [first] = section.stories;
  return h('section.desk.desk--6', { 'aria-labelledby': `desk-${desk(section.id).no}` }, deskHead(section),
    h('div.desk__body', h('div.desk__first', storyCard(first, { step: WIDE_STEP[tier(first.sourceCount)], cov: 'foot', day }), covFoot(first)), h('div.desk__stack')));
}

function tape(marketsStrip) {
  if (!marketsStrip?.quotes?.length) return null;
  return h('section.tape', { 'aria-labelledby': 'tape-h' }, h('div.wrap.grid.tape__in',
    h('div.tape__head', h('h2.tape__title#tape-h', 'Markets at close'),
      marketsStrip.quotes.some((q) => q.stale) && h('span.label.is-stale', 'Some figures could not be refreshed'),
      h('span.label', marketsStrip.asOf ? longDate(marketsStrip.asOf).replace(/ \d{4}$/, '') : '', h('span.opt', ' · dotted line is the level a month ago')),
      h('a.more.label', { href: '#/markets' }, h('b', 'All markets'), h('kbd', { 'aria-hidden': 'true' }, 'M'))),
    marketsStrip.quotes.slice(0, 6).map((q) => h('div.quote',
      h('p.quote__name.label', q.short || q.name),
      h('p.quote__last', fmtNumber(q.price, q.price < 10 ? 4 : 2, q.currency)),
      spark(q.spark, { label: `${q.name} over the past month` }),
      h('p.quote__chg.data', chg(q.changePct))))));
}

async function claudeBlock(card) {
  if (!card) return null;
  const head = (note) => h('header.claude__head', h('span.tile', { 'aria-hidden': 'true' }, 'C'), h('h2.claude__name#claude-h', 'Claude Desk'), h('span.label', note));
  if (card.kind === 'update' && card.update) {
    const u = card.update;
    return h('section.claude', { 'aria-labelledby': 'claude-h' }, head('New from Claude'),
      h('div.claude__pitch', h('h3.claude__title', smart(u.title)), h('p.claude__when', smart(u.summary || ''))),
      h('div.claude__work', h('p.claude__links',
        outLink(u.url, { class: 'readon' }, 'Read the release note ', arw('ne')),
        (u.features || []).slice(0, 2).map((id) => h('a.readon', { href: `#/claude/feature/${id}` }, 'How to use it ', arw('right'))),
        h('a.readon', { href: '#/claude/updates' }, 'Everything new ', arw('right')))));
  }
  const book = await data.playbook();
  const feature = book.features.find((item) => item.id === card.featureId) || book.features[0];
  if (!feature) return null;
  return h('section.claude', { 'aria-labelledby': 'claude-h' }, head('One technique to try at work today'),
    h('div.claude__pitch',
      h('h3.claude__title', h('a', { href: `#/claude/feature/${feature.id}` }, smart(feature.title))),
      whenLine(feature.when || feature.summary),
      adoptControl(feature.id, 'front')),
    h('div.claude__work', feature.example ? promptBlock(feature.example, feature.example_kind) : h('p.claude__when', smart(feature.summary || '')),
      h('p.claude__links', h('a.readon', { href: `#/claude/feature/${feature.id}` }, 'Steps, pitfalls and docs ', arw('right')))));
}


export async function frontView(el, params, ctx) {
  const manifest = await data.manifest();
  const date = params.date && data.isDay(params.date) ? params.date : (params.date ? 'none' : manifest.edition?.date);
  if (!date) {
    ctx.setPage({ title: 'Front Page', kicker: 'No edition yet', nav: 'front' });
    el.append(h('div.wrap', notice('No edition has been set yet.', 'The first edition is set by the first build after six in the morning. The Wire is already moving.',
      h('a.readon', { href: '#/wire' }, 'Open The Wire ', arw('right')))));
    return undefined;
  }
  let edition;
  try {
    edition = await data.edition(date);
  } catch {
    const when = data.isDay(date) ? longDate(fromDay(date)) : 'that date';
    ctx.setPage({ title: 'Front Page', kicker: data.isDay(date) ? when : 'No such edition', nav: 'front' });
    el.append(h('div.wrap', notice(`There is no edition for ${when}.`, 'It may be older than the archive, or the build did not run that day.',
      h('a.readon', { href: '#/archive' }, 'Back Issues ', arw('right')))));
    return undefined;
  }
  const isToday = date === manifest.edition?.date;
  const stories = editionStories(edition);
  const count = stories.length;
  const minutes = edition.stats?.readMinutes || Math.max(1, Math.round(count / 6));
  const [marketsData, hot] = await Promise.all([data.markets(), data.loadOr('latest.json', { stories: [] })]);
  const strip = edition.markets?.quotes?.length ? edition.markets : null;
  const wireNew = hot.stories.filter((story) => Date.parse(story.updatedAt || story.publishedAt) > Date.parse(edition.generatedAt)).length;

  ctx.setFrontPlate({
    date, number: edition.number, count, minutes, generatedAt: edition.generatedAt,
    next: isToday ? `Next: ${nextEdition(manifest)}` : 'Back issue',
    quotes: (strip?.quotes || marketsData?.groups?.flatMap((group) => group.quotes).filter((q) => (marketsData.strip || []).includes(q.symbol)) || []),
    asOf: strip?.asOf || marketsData?.generatedAt,
  });

  const key = [1, 3, 6, 9].map((k) => h('span.cov', ticks(k), h('span', String(k))));
  const page = h('div.wrap',
    folio([h('b', isToday ? 'Front Page' : 'Back issue'), ' · ', h('span.opt', 'Edition '), `No. ${edition.number} · ${count} stories`, h('span.opt', ` · about ${minutes} minutes · it ends`)],
      [h('span', 'Key', h('span.long', ': the more outlets carry a story, the bigger it is set')), ...key]),
    !isToday && h('p.backissue.label', h('b', `You are reading the edition of ${longDate(fromDay(date))}.`), ' ', h('a.more', { href: '#/' }, h('b', 'Today’s edition'), arw('right'))),
    h('h2.vh', 'Front page'),
    h('div.grid.front', leadBlock(edition.lead, date), seconds(edition.front || [], date), briefs(edition.briefs || [], edition, isToday ? wireNew : 0)));
  const rows = deskRows(edition.sections || [], date);
  const tapeEl = tape(strip || (marketsData && { asOf: marketsData.generatedAt, quotes: marketsData.groups.flatMap((g) => g.quotes).filter((q) => (marketsData.strip || []).includes(q.symbol)) }));
  page.append(...rows.slice(0, 2));
  el.append(page);
  if (tapeEl) el.append(tapeEl);
  const rest = h('div.wrap', ...rows.slice(2));
  const claude = await claudeBlock(edition.claude);
  if (claude) rest.append(claude);
  if (edition.weekend) {
    rest.append(h('p.weekend-flag', h('span.tile', { 'aria-hidden': 'true' }, 'R'), h('a', { href: `#/weekend/${edition.weekend.isoWeek}` },
      h('b', 'Weekend Review is out. '), smart(edition.weekend.title || 'The five papers of the week'), ' ', arw('right'))));
  }
  rest.append(h('footer.end',
    h('p.end__mark', { 'aria-label': 'End of edition' }, '— 30 —'),
    h('p.end__line', `That’s the edition. ${count} stories, about ${minutes} ${plural(minutes, 'minute')}.`),
    h('p.end__next.label', h('span', isToday ? `Next edition ${nextEdition(manifest)}` : `Set ${shortDate(edition.generatedAt)} ${clock(edition.generatedAt)} ${zoneName()}`),
      h('a.more', { href: '#/wire' }, h('b', 'The Wire is still moving'), arw('right')),
      h('a.more', { href: '#/archive' }, h('b', 'Back Issues'), arw('right')))));
  el.append(rest);

  return trackSeen(el, date, count);
}

function nextEdition(manifest) {
  const hour = String(manifest.site?.editionHour ?? 6).padStart(2, '0');
  return `tomorrow ${hour}:00 ${zoneName()}`;
}

/** Count a story as seen once it has been on screen for a moment; report "12 of 41" to the top bar. */
function trackSeen(el, date, total) {
  const seenKey = 'seen';
  const seen = new Set(store.get(seenKey, {})[date] || []);
  const report = () => shell.setSeen(Math.min(seen.size, total), total);
  report();
  if (!('IntersectionObserver' in window)) return undefined;
  const timers = new Map();
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      const id = entry.target.dataset.story;
      if (entry.isIntersecting && !seen.has(id)) {
        timers.set(id, setTimeout(() => {
          seen.add(id);
          store.update(seenKey, {}, (map) => {
            const days = Object.keys(map).sort().slice(-13); // keep two weeks of editions
            const next = Object.fromEntries(days.map((d) => [d, map[d]]));
            next[date] = [...seen];
            return next;
          });
          report();
        }, 1200));
      } else if (!entry.isIntersecting) {
        clearTimeout(timers.get(id));
      }
    }
  }, { threshold: 0.6 });
  for (const item of el.querySelectorAll('[data-story]')) observer.observe(item);
  return () => {
    observer.disconnect();
    for (const timer of timers.values()) clearTimeout(timer);
    shell.setSeen(0, 0);
  };
}

