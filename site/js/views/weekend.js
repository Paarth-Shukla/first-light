// Weekend Review: the five most-noticed CS and electronics papers of the week, with an extractive digest of each.

import { h, arw, outLink, append } from '../core/dom.js';
import * as data from '../core/data.js';
import * as shell from '../shell.js';
import { smart, folio, notice, chg, clipButton, plural, storyHref } from '../core/ui.js';
import { shortDate, fromDay } from '../core/time.js';

const TRACK = { cs: 'Computer science', electronics: 'Electronics and systems' };

function authors(list) {
  const names = list || [];
  if (names.length <= 6) return names.join(', ');
  return `${names.slice(0, 5).join(', ')} and ${names.length - 5} more`;
}

function paperCard(paper) {
  const digest = [paper.digest?.problem, paper.digest?.method, paper.digest?.result].filter((line, index, all) => line && all.indexOf(line) === index);
  if (!digest.length && paper.digest?.gist) digest.push(paper.digest.gist);
  const key = `paper:${paper.id}`;
  return h('article.paper', { dataset: { story: key } },
    h('span.paper__rank', { 'aria-label': `Rank ${paper.rank}` }, String(paper.rank)),
    h('div.paper__main',
      h('h3.paper__title', outLink(paper.links?.abs, { 'data-hl': true }, smart(paper.title))),
      h('p.paper__authors', authors(paper.authors)),
      h('ul.chips', { 'aria-label': 'Why it surfaced' },
        h('li.chip.chip--solid', `${TRACK[paper.track] || paper.track} · ${paper.primary}`),
        (paper.why || []).slice(0, 4).map((reason) => h('li.chip', reason))),
      h('p.paper__foot.label', h('b', `arXiv ${paper.id}`),
        paper.links?.pdf && outLink(paper.links.pdf, {}, 'PDF ', arw('ne')),
        paper.links?.code && outLink(paper.links.code, {}, 'Code ', arw('ne')),
        paper.links?.hn && outLink(paper.links.hn, {}, 'Discussion ', arw('ne')),
        clipButton(key, { kind: 'paper', id: paper.id, title: paper.title, url: paper.links?.abs, source: `arXiv ${paper.primary}` }))),
    h('ol.paper__digest', { 'aria-label': 'Lines lifted from the abstract' }, digest.map((line) => h('li', smart(line)))));
}

function runnerRow(paper) {
  return h('li.row', h('span.row__meta', h('span.tag.label', paper.primary), h('span.row__date', `Score ${Math.round(paper.score || 0)}`)),
    h('div.row__main', h('p.row__title', outLink(paper.links?.abs, { 'data-hl': true }, smart(paper.title))),
      h('p.row__sum', smart(paper.digest?.gist || authors(paper.authors)))),
    h('p.row__aside.label', (paper.why || []).slice(0, 1)));
}

export async function weekendView(el, params, ctx) {
  const index = await data.loadOr('weekend/index.json', { weeks: [] });
  const isoWeek = data.isWeek(params.week) ? params.week : (params.week ? null : index.weeks[0]?.isoWeek);
  if (params.week && !isoWeek) {
    ctx.setPage({ title: 'Weekend Review', kicker: 'No such issue', nav: 'weekend' });
    el.append(h('div.wrap.page', notice('There is no Weekend Review at that address.', null, h('a.readon', { href: '#/weekend' }, 'The latest issue ', arw('right')))));
    return;
  }
  if (!isoWeek) {
    ctx.setPage({ title: 'Weekend Review', kicker: 'Saturday’s reading list', nav: 'weekend' });
    el.append(h('div.wrap.page', notice('The first Weekend Review has not been set yet.', 'It is built on Saturday morning: the five papers in computer science and electronics that were most noticed during the week.')));
    return;
  }
  const issue = await data.loadOr(`weekend/${isoWeek}.json`, null);
  ctx.setPage({ title: 'Weekend Review', kicker: issue?.from && issue?.to ? `${shortDate(fromDay(issue.from))} to ${shortDate(fromDay(issue.to))}` : isoWeek, nav: 'weekend' });
  if (!issue || !Array.isArray(issue.papers)) {
    el.append(h('div.wrap.page', notice(`There is no Weekend Review for ${isoWeek}.`, null, h('a.readon', { href: '#/weekend' }, 'The latest issue ', arw('right')))));
    return;
  }
  const review = issue.review || {};
  append(el, h('div.wrap.page',
    folio([h('b', 'Weekend Review'), ` · ${isoWeek} · five papers, at least two from electronics and systems`],
      index.weeks.length > 1 && [h('label.label', 'Issue ', h('select.picker', { onchange: (event) => { location.hash = `#/weekend/${event.target.value}`; } },
        index.weeks.map((week) => h('option', { value: week.isoWeek, selected: week.isoWeek === isoWeek }, `${week.isoWeek} · ${shortDate(fromDay(week.to))}`))))]),
    h('p.method', smart(issue.method || '')),
    h('div.papers', (issue.papers || []).map(paperCard)),
    (issue.runnersUp || []).length ? h('section.block', h('header.block__head', h('h2.block__title', 'Runners-up'), h('span.label', `${issue.runnersUp.length} more that came close`)),
      h('ol.rows', issue.runnersUp.map(runnerRow))) : null,
    (review.stories || []).length ? h('section.block', h('header.block__head', h('h2.block__title', 'The week in stories')),
      h('ol.rows', review.stories.map((story) => h('li.row',
        h('span.row__meta', h('time.row__date', { datetime: story.day }, shortDate(fromDay(story.day))), h('span.tag.label', `${story.sourceCount || 1} ${plural(story.sourceCount || 1, 'outlet')}`)),
        h('div.row__main', h('p.row__title', outLink(story.url, { 'data-hl': true }, smart(story.title)))),
        h('p.row__aside.label', h('a.more', { href: storyHref(story) }, h('b', 'Who carried it'), arw('right'))))))) : null,
    (review.markets || []).length ? h('section.block', h('header.block__head', h('h2.block__title', 'The week on the tape')),
      h('div.tablewrap', h('table.mkt.mkt--week', h('thead', h('tr.label', h('th', { scope: 'col' }, 'Instrument'), h('th', { scope: 'col' }, 'Week'))),
        h('tbody', review.markets.map((row) => h('tr', h('td', h('span.mkt__name', h('b', row.name))), h('td.data', chg(row.weekPct)))))))) : null,
    (review.claude || []).length ? h('section.block', h('header.block__head', h('h2.block__title', 'Claude this week'), h('a.more.label', { href: '#/claude/updates' }, h('b', 'All updates'), arw('right'))),
      h('ol.rows', review.claude.map((entry) => h('li.row',
        h('span.row__meta', h('time.row__date', { datetime: entry.date }, shortDate(fromDay(entry.date)))),
        h('div.row__main', h('p.row__title', outLink(entry.url, { 'data-hl': true }, smart(entry.title))), entry.summary && h('p.row__sum', smart(entry.summary))),
        h('p.row__aside.label', arw('ne')))))) : null));
}
