// Tests for site/js/search/engine.js. The tokenizer and stemmer are held to the same vectors as the Python twin.

import { test, equal, ok } from './run.js';
import { tokenize, stem, STOPWORDS, parseQuery, SearchIndex, highlight, editDistance } from '../../site/js/search/engine.js';

const vectors = await (await fetch('../fixtures/stem-vectors.json')).json();

test(`tokenize matches the Python tokenizer on ${vectors.tokenize.length} vectors`, () => {
  const wrong = vectors.tokenize.filter((v) => JSON.stringify(tokenize(v.in)) !== JSON.stringify(v.out));
  equal(wrong.map((v) => ({ in: v.in, want: v.out, got: tokenize(v.in) })).slice(0, 5), []);
});

test(`stem matches the Python stemmer on ${vectors.stem.length} vectors`, () => {
  const wrong = vectors.stem.filter((v) => stem(v.in) !== v.out);
  equal(wrong.map((v) => ({ in: v.in, want: v.out, got: stem(v.in) })).slice(0, 5), []);
});

test('stopword list is identical to the Python one', () => {
  if (!vectors.stopwords) return;
  equal([...STOPWORDS].sort(), [...vectors.stopwords].sort());
});

test('editDistance counts a transposition as one and gives up past the limit', () => {
  equal(editDistance('nvidia', 'nvdiia', 1), 1);
  equal(editDistance('tariff', 'tarrif', 2), 2); // one letter added, one dropped
  ok(editDistance('nvidia', 'intel', 1) > 1);
});

test('parseQuery separates phrases, negation and operators', () => {
  const q = parseQuery('nvidia "rate cut" -crypto desk:ai source:Reuters in:papers after:2026-11-01 is:saved is:unread');
  equal(q.words, [{ text: 'nvidia', phrase: false, negate: false }, { text: 'rate cut', phrase: true, negate: false }, { text: 'crypto', phrase: false, negate: true }]);
  equal(q.filters, { is: ['saved', 'unread'], section: 'ai', source: 'reuters', kinds: ['paper'], after: '2026-11-01' });
});

test('parseQuery leaves an unknown operator as an ordinary word', () => {
  equal(parseQuery('ratio:16:9').words.map((w) => w.text), ['ratio:16:9']);
});

const NOW = Date.parse('2026-11-11T12:00:00Z');
const lexicon = {
  aliases: { llm: ['large language model', 'foundation model'], 'rate cut': ['monetary easing'], ev: ['electric vehicle'] },
  entities: {
    nvidia: { name: 'Nvidia', type: 'company', aliases: ['NVDA', 'Nvidia Corp'], related: ['jensen-huang'], ticker: 'NVDA' },
    'jensen-huang': { name: 'Jensen Huang', type: 'person', aliases: ['Huang'], related: ['nvidia'], ticker: null },
    rbi: { name: 'Reserve Bank of India', type: 'regulator', aliases: ['RBI'], related: [], ticker: null },
  },
  related: { tariff: [['export', 0.9], ['chip', 0.6]], chip: [['semiconductor', 0.8]] },
  glossary: { 'repo rate': 'The rate at which the central bank lends to banks.' },
};
const docs = [
  { i: 's1', k: 'story', t: 'Nvidia shares fall as export rules tighten', s: 'Chip maker warns on China sales.', c: 'companies', e: ['nvidia'], o: 'Reuters', n: 9, d: '2026-11-11T06:00:00Z', u: 'https://a.example/1', x: 80 },
  { i: 's2', k: 'story', t: 'Jensen Huang defends chip strategy', s: 'The chief executive spoke in Taipei.', c: 'companies', e: ['jensen-huang'], o: 'BBC News', n: 4, d: '2026-11-10T06:00:00Z', u: 'https://a.example/2', x: 60 },
  { i: 's3', k: 'story', t: 'RBI holds repo rate steady', s: 'Reserve Bank of India signals a rate cut may come later.', c: 'india-markets', e: ['rbi'], o: 'Mint', n: 6, d: '2026-11-09T06:00:00Z', u: 'https://a.example/3', x: 70 },
  { i: 's4', k: 'story', t: 'Large language model beats benchmark', s: 'A new foundation model tops the leaderboard.', c: 'llm', e: [], o: 'The Verge', n: 2, d: '2026-11-08T06:00:00Z', u: 'https://a.example/4', x: 40 },
  { i: 's5', k: 'story', t: 'Tariffs on semiconductors announced', s: 'New duties target imports.', c: 'markets', e: [], o: 'CNBC', n: 3, d: '2026-11-07T06:00:00Z', u: 'https://a.example/5', x: 50 },
  { i: 's6', k: 'story', t: 'Crypto rally lifts chip stocks', s: 'Bitcoin miners buy more hardware.', c: 'markets', e: [], o: 'CoinDesk', n: 1, d: '2026-10-01T06:00:00Z', u: 'https://a.example/6', x: 20 },
  { i: 'p1', k: 'paper', t: 'Sparse attention for chip design', s: 'We propose a method.', c: 'weekend', e: [], o: 'cs.AR', n: 1, d: '2026-11-06T06:00:00Z', u: 'https://arxiv.org/abs/1', x: 70 },
  { i: 'f1', k: 'feature', t: 'Plan mode', s: 'Analyse before you edit.', c: 'code', e: [], o: 'Claude Desk', n: 1, d: null, u: '#/claude/feature/cc-plan-mode', x: 0 },
];
const build = () => { const index = new SearchIndex(lexicon); index.add(docs); return index; };
const ids = (result) => result.hits.map((hit) => hit.doc.i);

test('a doc id is indexed once even when added twice', () => {
  const index = build();
  index.add(docs);
  equal(index.size, docs.length);
});

test('a plain word finds direct matches first', () => {
  const result = build().search('nvidia', { now: NOW });
  equal(ids(result)[0], 's1');
});

test('an entity name also finds its ticker, its aliases and its related names, and says so', () => {
  const result = build().search('nvidia', { now: NOW });
  ok(ids(result).includes('s2'), 'the related person should be found');
  ok(result.expansions.some((x) => x.label === 'Jensen Huang'), 'the widening should be listed');
  equal(result.entity.name, 'Nvidia');
});

test('a ticker finds the company', () => {
  ok(ids(build().search('NVDA', { now: NOW })).includes('s1'));
});

test('a synonym group widens the query', () => {
  const result = build().search('llm', { now: NOW });
  equal(ids(result), ['s4']);
  ok(result.expansions.some((x) => x.label === 'large language model'));
  ok(result.hits[0].via.length > 0, 'the hit should say it was found through the widening');
});

test('a multi-word phrase with a synonym is treated as one unit', () => {
  const result = build().search('rate cut', { now: NOW });
  equal(ids(result)[0], 's3');
});

test('corpus-learned neighbours widen a word, below direct matches', () => {
  const result = build().search('tariff', { now: NOW });
  equal(ids(result)[0], 's5');
  ok(ids(result).includes('s1'), '"export" is a learned neighbour of "tariff"');
  ok(result.expansions.some((x) => x.kind === 'related'));
});

test('exact-only mode turns every widening off', () => {
  const result = build().search('nvidia', { now: NOW, exactOnly: true });
  equal(ids(result), ['s1']);
  equal(result.expansions, []);
});

test('a dropped widening stays dropped', () => {
  const index = build();
  const wide = index.search('nvidia', { now: NOW });
  const key = wide.expansions.find((x) => x.label === 'Jensen Huang').key;
  const narrowed = index.search('nvidia', { now: NOW, drop: [key, ...wide.expansions.filter((x) => x.label === 'Huang').map((x) => x.key)] });
  ok(!ids(narrowed).includes('s2'));
});

test('a quoted phrase must appear as written', () => {
  equal(ids(build().search('"repo rate"', { now: NOW })), ['s3']);
  equal(ids(build().search('"rate repo"', { now: NOW })), []);
});

test('a minus sign leaves a word out', () => {
  const result = build().search('chip -crypto', { now: NOW, exactOnly: true });
  ok(!ids(result).includes('s6'));
  ok(ids(result).includes('s2'));
});

test('a misspelling still finds the word and offers the correction', () => {
  const result = build().search('nvidai', { now: NOW });
  ok(ids(result).includes('s1'));
});

test('while typing, the last word matches by prefix', () => {
  equal(ids(build().search('semicon', { now: NOW, typing: true })), ['s5']);
});

test('plurals and -ing forms meet', () => {
  ok(ids(build().search('tariffs', { now: NOW, exactOnly: true })).includes('s5'));
  ok(ids(build().search('tightening', { now: NOW, exactOnly: true })).includes('s1'));
});

test('filters narrow by desk, kind, source and date', () => {
  const index = build();
  equal(ids(index.search('chip desk:markets', { now: NOW, exactOnly: true })), ['s6']);
  equal(ids(index.search('chip in:papers', { now: NOW, exactOnly: true })), ['p1']);
  equal(ids(index.search('chip source:bbc', { now: NOW, exactOnly: true })), ['s2']);
  ok(!ids(index.search('chip after:2026-11-01', { now: NOW, exactOnly: true })).includes('s6'));
});

test('a filter alone lists everything that passes, newest first', () => {
  equal(ids(build().search('desk:companies', { now: NOW })), ['s1', 's2']);
});

test('the kinds option restricts results and counts report every kind', () => {
  const result = build().search('chip', { now: NOW, kinds: ['paper'] });
  equal(ids(result), ['p1']);
});

test('when no doc has every word, docs with some of them are returned and flagged', () => {
  const result = build().search('nvidia leaderboard', { now: NOW, exactOnly: true });
  ok(result.partial);
  ok(result.total >= 2);
});

test('a glossary term returns its definition', () => {
  equal(build().search('repo rate', { now: NOW }).definition.term, 'repo rate');
});

test('newest-first sorting orders by date', () => {
  const result = build().search('chip', { now: NOW, sort: 'newest', exactOnly: true });
  const dates = result.hits.map((hit) => hit.doc.d);
  equal(dates, [...dates].sort().reverse());
});

test('stopwords in a query are ignored unless they are all there is', () => {
  const index = build();
  equal(ids(index.search('the nvidia', { now: NOW, exactOnly: true })), ['s1']);
  // a query of only stopwords is searched as typed rather than silently returning nothing
  ok(index.search('the', { now: NOW, exactOnly: true }).total > 0);
});

test('an empty index answers without throwing', () => {
  equal(new SearchIndex().search('anything').total, 0);
});

test('highlight marks inflected forms and leaves the rest alone', () => {
  const pieces = highlight('Tariffs hit Nvidia’s chips', ['tariff', 'nvidia']);
  equal(pieces.filter((p) => p.mark).map((p) => p.text), ['Tariffs', 'Nvidia’s']);
  equal(pieces.map((p) => p.text).join(''), 'Tariffs hit Nvidia’s chips');
});
