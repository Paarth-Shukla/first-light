// Markets: end-of-day figures in ledger tables, and the movers joined to the stories that explain them.

import { h, arw } from '../core/dom.js';
import * as data from '../core/data.js';
import * as shell from '../shell.js';
import { chg, spark, fmtNumber, folio, notice, smart, plural } from '../core/ui.js';
import { clock, shortDate, zoneName, hoursSince } from '../core/time.js';

const digitsFor = (q) => (q.kind === 'fx' && q.price < 10 ? 4 : 2);

function rangeCell(q) {
  if (!(q.high52 > q.low52)) return h('td.data', '–');
  const at = Math.max(0, Math.min(100, ((q.price - q.low52) / (q.high52 - q.low52)) * 100));
  return h('td.data', h('span.range', { style: `--at:${at.toFixed(0)}%`, title: `52-week range ${fmtNumber(q.low52, digitsFor(q), q.currency)} to ${fmtNumber(q.high52, digitsFor(q), q.currency)}` }, h('i')));
}

function table(group) {
  return h('section.block', { 'aria-labelledby': `mk-${group.id}` },
    h('header.block__head', h('h2.block__title', { id: `mk-${group.id}` }, group.name)),
    h('div.tablewrap', h('table.mkt',
      h('caption.vh', `${group.name}, latest close`),
      h('thead', h('tr.label', ['Instrument', 'Last', 'Change', 'Points', '52-week range', 'Past month'].map((name) => h('th', { scope: 'col' }, name)))),
      h('tbody', group.quotes.map((q) => h(`tr${q.stale ? '.is-stale' : ''}`,
        h('td', h('span.mkt__name', h('b', q.short || q.name), h('span.label', q.stale ? 'Stale' : (q.currency || q.exchange || '')))),
        h('td.data.mkt__last', fmtNumber(q.price, digitsFor(q), q.currency)),
        h('td.data', chg(q.changePct)),
        h('td.data', q.change === null || q.change === undefined ? '–' : `${q.change > 0 ? '+' : q.change < 0 ? '−' : ''}${fmtNumber(Math.abs(q.change), digitsFor(q), q.currency)}`),
        rangeCell(q),
        h('td', spark(q.spark, { w: 120, height: 28, label: `${q.name} over the past month` }))))))));
}

export async function marketsView(el, params, ctx) {
  ctx.setPage({ title: 'Markets', kicker: 'Figures at the latest close', nav: 'markets' });
  const m = await data.markets();
  if (!m?.groups?.length) {
    el.append(h('div.wrap.page', notice('No market figures yet.', 'The markets stage of the pipeline has not produced a file. Sources for prices are unofficial and can be unavailable.')));
    return;
  }
  const old = hoursSince(m.generatedAt) > 30;
  const movers = m.movers || [];
  el.append(h('div.wrap.page',
    folio([h('b', 'Markets'), ` · fetched ${shortDate(m.generatedAt)} ${clock(m.generatedAt)} ${zoneName()} · end-of-day figures, not live, not advice`],
      (m.stale || old) && [h('span.is-stale', m.stale ? 'Most figures could not be refreshed: showing the last good values' : 'These figures are more than a day old')]),
    movers.length ? h('section.block', { 'aria-labelledby': 'movers-h' },
      h('header.block__head', h('h2.block__title#movers-h', 'Movers, with reasons'), h('span.label', `${movers.length} ${plural(movers.length, 'move')} past the threshold`)),
      h('ol.rows', movers.map((mover) => h('li.row',
        h('span.row__meta.data', chg(mover.changePct)),
        h('div.row__main', h('p.row__title', mover.name),
          mover.story ? h('p.row__sum', h('a', { href: `#/story/${mover.story.id}` }, smart(mover.story.title)), mover.story.sourceCount ? ` · ${mover.story.sourceCount} ${plural(mover.story.sourceCount, 'outlet')}` : '')
            : h('p.row__sum.is-quiet', 'Moved; no linked story found.')),
        h('p.row__aside.label', h('b', mover.symbol)))))) : null,
    m.groups.filter((group) => group.quotes?.length).map(table),
    h('p.label.footnote', 'The dotted line on each chart is the level a month ago; the dot is the latest close. Day change is the provider’s figure. ',
      h('a.more', { href: '#/s/markets' }, h('b', 'Markets desk'), arw('right')), ' ', h('a.more', { href: '#/s/india-markets' }, h('b', 'Dalal Street desk'), arw('right')))));
}
