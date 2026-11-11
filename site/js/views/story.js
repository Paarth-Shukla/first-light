// One story, opened up: every outlet that carried it, why it ranked where it did, and its earlier days.

import { h, arw, outLink } from '../core/dom.js';
import * as data from '../core/data.js';
import * as store from '../core/store.js';
import * as shell from '../shell.js';
import { desk, ticks, headline, summarize, smart, plural, folio, notice, chg, fmtNumber, storyKey, storySnapshot, clipButton } from '../core/ui.js';
import { clock, shortDate, fromDay, zoneName } from '../core/time.js';

const SIGNALS = [
  ['breadth', 'Breadth', 'How many outlets carried it, weighted towards the better ones'],
  ['tier', 'Source', 'The standing of the best outlet that carried it'],
  ['recency', 'Recency', 'How recently it moved'],
  ['velocity', 'Velocity', 'How fast outlets picked it up in the first six hours'],
  ['attention', 'Attention', 'Discussion on Hacker News'],
  ['editorial', 'Placement', 'How high it sits on curated front pages'],
];

export async function storyView(el, params, ctx) {
  const story = await data.findStory(params.id, params.query.d);
  if (!story) {
    ctx.setPage({ title: 'Story not on file', kicker: 'The Wire' });
    el.append(h('div.wrap.page', notice('That story is not on file.', 'It may be older than the 90-day archive.', h('a.readon', { href: '#/wire' }, 'Open The Wire ', arw('right')))));
    return;
  }
  const d = desk(story.section);
  const n = story.sourceCount || 1;
  ctx.setPage({ title: 'Who carried it', kicker: `Desk ${d.no} · ${d.name}`, desk: d.id, docTitle: story.title });
  const [marketsData, lexicon] = await Promise.all([data.markets(), data.loadOr('search/lexicon.json', { entities: {} })]);
  const quotes = (marketsData?.groups || []).flatMap((group) => group.quotes).filter((q) => (story.tickers || []).includes(q.symbol));
  const summary = summarize(story.summary, 3);
  el.append(h('div.wrap.page',
    folio([h('a.more', { href: `#/s/${d.id}` }, arw('left'), h('b', ` ${d.name} desk`))], [clipButton(storyKey(story), storySnapshot(story))]),
    h('article.grid.detail', { dataset: { story: story.id } },
      h('div.detail__main',
        h('p.story__meta.label', h('span', h('b', d.no), ` ${d.name}`), h('time', { datetime: story.publishedAt }, `${shortDate(story.publishedAt)} ${clock(story.publishedAt)} ${zoneName()}`)),
        h('h2.story__hl.hl-6', outLink(story.url, { 'data-hl': true, onclick: () => store.markRead(story.id) }, headline(story.title))),
        summary && h('p.lead__deck', summary),
        h('p.lead__acts', outLink(story.url, { class: 'readon', onclick: () => store.markRead(story.id) }, `Read at ${story.sources?.[0]?.name || 'source'} `, arw('ne'))),
        h('h3.block__sub.label', h('b', `Carried by ${n} ${plural(n, 'outlet')}`)),
        h('ol.rows', (story.sources || []).map((source) => h('li.row',
          h('span.row__meta', h('span.tag.label', `Tier ${source.tier || 3}`), h('time.row__date', { datetime: source.publishedAt }, `${shortDate(source.publishedAt)} ${clock(source.publishedAt)}`)),
          h('div.row__main', h('p.row__title', outLink(source.url, { 'data-hl': true }, smart(source.title || story.title))), h('p.row__sum', source.name)),
          h('p.row__aside.label', arw('ne'))))),
        story.thread?.history?.length ? [
          h('h3.block__sub.label', h('b', `A continuing story · day ${story.thread.day}`)),
          h('ol.rows', story.thread.history.map((beat) => h('li.row',
            h('span.row__meta', h('time.row__date', { datetime: beat.date }, shortDate(fromDay(beat.date)))),
            h('div.row__main', h('p.row__title', h('a', { href: `#/story/${beat.id}?d=${beat.date}` }, smart(beat.title)))),
            h('p.row__aside.label', arw('right')))))] : null),
      h('aside.detail__side',
        h(`div.cov-xl${n >= 10 ? '.cov-xl--wide' : ''}`, h('span.cov-xl__n', String(n)), h('span.cov-xl__what', ticks(n), h('span.label', plural(n, 'outlet'), h('br'), 'carried', h('br'), 'this'))),
        h('h3.label', h('b', 'Why it is here')),
        (story.why || []).length ? h('ul.chips', story.why.map((reason, index) => h(`li.chip${index ? '' : '.chip--solid'}`, reason))) : null,
        h('table.signals.data', h('caption.vh', 'Ranking signals, each from 0 to 100'),
          h('tbody', SIGNALS.map(([key, name, help]) => {
            const value = Math.round(((story.signals || {})[key] || 0) * 100);
            return h('tr', { title: help }, h('th', { scope: 'row' }, name), h('td', h('span.meter', { style: `--v:${value}%` }, h('i'))), h('td', String(value)));
          }))),
        h('p.label', h('b', `Score ${Math.round(story.score || 0)}`), ' of 100. The weights are in config/site.json.'),
        (story.entities || []).length ? [h('h3.label', h('b', 'Names in it')),
          h('p.taglist', story.entities.slice(0, 12).map((id) => h('a.chip', { href: `#/search?q=${encodeURIComponent(lexicon.entities?.[id]?.name || id)}` }, lexicon.entities?.[id]?.name || id)))] : null,
        quotes.length ? [h('h3.label', h('b', 'On the tape')),
          h('table.quotes.data', h('tbody', quotes.map((q) => h('tr', h('th', { scope: 'row' }, q.short || q.name), h('td.last-cell', fmtNumber(q.price, 2, q.currency)), h('td.chg-cell', chg(q.changePct))))))] : null))));
}
