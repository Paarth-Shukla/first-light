// The search engine. Pure functions and one class; no DOM, no network, so it runs in a worker,
// on the main thread, and in the test page alike.
// tokenize() and stem() mirror pipeline/core/textutil.py exactly; tests/fixtures/stem-vectors.json holds both to it.

export const STOPWORDS = new Set(`a about above across after again against all almost also although always am among an and
another any are aren around as at be because been before being below between both but by can
cannot could couldn did didn do does doesn doing don down during each either even ever every
few for from further had hadn has hasn have haven having he her here hers herself him himself
his how however i if in into is isn it its itself just ll may me might more most much must my
myself neither no nor not now of off often on once only or other our ours ourselves out over
own per rather re same shall she should shouldn since so some still such than that the their
theirs them themselves then there these they this those though through to too toward towards
under until up upon ve very was wasn we were weren what when where whether which while who
whom whose why will with within without won would wouldn yet you your yours yourself yourselves
says said new report reports amid via video watch live update updates`.split(/\s+/));

const CANDIDATE = /[a-z0-9]+(?:[&.\-][a-z0-9]+)*(?:\++(?![a-z0-9+]))?/g;
const DIGIT = /[0-9]/;

export function tokenize(text) {
  const folded = String(text ?? '').normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const tokens = [];
  for (const match of folded.matchAll(CANDIDATE)) {
    const candidate = match[0];
    const parts = DIGIT.test(candidate) ? [candidate] : candidate.split(/[.\-]/);
    for (const part of parts) if (part.length > 1 || /^[0-9]$/.test(part)) tokens.push(part);
  }
  return tokens;
}

function stripPlural(word) {
  if (word.endsWith('ies') && word.length > 4) return `${word.slice(0, -3)}y`;
  if (word.endsWith('sses')) return word.slice(0, -2);
  if (/(xes|ches|shes|zes)$/.test(word)) return word.slice(0, -2);
  if (word.endsWith('s') && !/(ss|us|is)$/.test(word)) return word.slice(0, -1);
  return word;
}

function undouble(word) {
  const last = word[word.length - 1];
  if (word[word.length - 2] === last && last >= 'a' && last <= 'z' && !'aeioulsz'.includes(last)) return word.slice(0, -1);
  return word;
}

export function stem(token) {
  if (token.length <= 3 || DIGIT.test(token)) return token;
  const word = stripPlural(token);
  for (const [suffix, fix] of [['ing', true], ['ed', true], ['ly', false]]) {
    if (word.endsWith(suffix) && word.length - suffix.length >= 4) {
      const base = word.slice(0, -suffix.length);
      return fix ? undouble(base) : base;
    }
  }
  return word;
}

export const stems = (text) => tokenize(text).map(stem);

/** Damerau-Levenshtein distance, giving up (returning max + 1) as soon as it exceeds `max`. */
export function editDistance(a, b, max) {
  if (Math.abs(a.length - b.length) > max) return max + 1;
  let prev2 = null;
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const row = [i];
    let best = i;
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      let value = Math.min(prev[j] + 1, row[j - 1] + 1, prev[j - 1] + cost);
      if (prev2 && i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) value = Math.min(value, prev2[j - 2] + 1);
      row.push(value);
      if (value < best) best = value;
    }
    if (best > max) return max + 1;
    prev2 = prev;
    prev = row;
  }
  return prev[b.length];
}

// ---- query language --------------------------------------------------------

const KIND_ALIASES = {
  __proto__: null, // so that "in:constructor" is an unknown kind, not Object.prototype.constructor
  story: ['story'], stories: ['story'], news: ['story'], paper: ['paper'], papers: ['paper'],
  claude: ['update', 'feature', 'recipe'], update: ['update'], updates: ['update'], feature: ['feature'],
  features: ['feature'], recipe: ['recipe'], recipes: ['recipe'], term: ['term'], glossary: ['term'],
};

/**
 * "nvidia export -tariff desk:ai after:2026-11-01 "rate cut"" →
 * { words: [{text, phrase, negate}], filters: {section, source, kinds, after, before, is: []} }
 */
export function parseQuery(query) {
  const filters = { is: [] };
  const words = [];
  const pattern = /(-?)(?:"([^"]+)"|(\S+))/g;
  for (const match of String(query || '').matchAll(pattern)) {
    const negate = match[1] === '-';
    if (match[2] !== undefined) { words.push({ text: match[2], phrase: true, negate }); continue; }
    const word = match[3];
    const op = /^([a-z]+):(.+)$/i.exec(word);
    if (op && !negate) {
      const key = op[1].toLowerCase();
      const value = op[2].toLowerCase();
      if (key === 'desk' || key === 'section' || key === 'cat') { filters.section = value; continue; }
      if (key === 'source') { filters.source = value; continue; }
      if (key === 'in' || key === 'kind' || key === 'type') { if (KIND_ALIASES[value]) { filters.kinds = KIND_ALIASES[value]; continue; } }
      if (key === 'after' && /^\d{4}-\d{2}-\d{2}$/.test(value)) { filters.after = value; continue; }
      if (key === 'before' && /^\d{4}-\d{2}-\d{2}$/.test(value)) { filters.before = value; continue; }
      if (key === 'is') { filters.is.push(value); continue; }
    }
    words.push({ text: word, phrase: false, negate });
  }
  return { words, filters };
}

const dayFormatters = new Map();

/** The calendar day of an ISO timestamp in a timezone ("2026-11-11"); UTC when no usable timezone is given. */
export function localDay(iso, timeZone) {
  if (!timeZone) return iso.slice(0, 10);
  if (!dayFormatters.has(timeZone)) {
    let formatter = null;
    try { formatter = new Intl.DateTimeFormat('en-CA', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' }); } catch { formatter = null; }
    dayFormatters.set(timeZone, formatter);
  }
  const formatter = dayFormatters.get(timeZone);
  const date = new Date(iso);
  return formatter && !Number.isNaN(date.getTime()) ? formatter.format(date) : iso.slice(0, 10);
}

// ---- the index ---------------------------------------------------------------

const FIELD_WEIGHT = { title: 3, entity: 2, summary: 1, source: 0.5 };
const K1 = 1.2;
const B = 0.6;
const WEIGHT = { direct: 1, entity: 1, alias: 0.8, relatedEntity: 0.45, related: 0.35, prefix: 0.7, fuzzy: 0.6 };

export class SearchIndex {
  /** lexicon: {aliases, entities, related, glossary} from data/search/lexicon.json (any part may be missing). */
  constructor(lexicon = {}) {
    // null-prototype copies: a query word such as "constructor" must not find Object.prototype members
    const bare = (part) => Object.assign(Object.create(null), part || {});
    this.lexicon = { aliases: bare(lexicon.aliases), entities: bare(lexicon.entities), related: bare(lexicon.related), glossary: bare(lexicon.glossary) };
    this.docs = [];
    this.ids = new Set();
    this.sections = new Set(); // every doc's section or surface, so desk:india is not also desk:india-markets
    this.postings = new Map(); // stem -> Map(doc index -> weighted term frequency)
    this.lengths = [];
    this.totalLength = 0;
    this.surface = new Map(); // normalised phrase -> entity id, for "is this query an entity?"
    for (const [id, entity] of Object.entries(this.lexicon.entities)) {
      for (const form of [entity.name, ...(entity.aliases || [])]) {
        const key = tokenize(form).join(' ');
        if (key && !this.surface.has(key)) this.surface.set(key, id);
      }
    }
    this.phrases = new Map(); // normalised phrase -> expansions (strings)
    for (const [term, expansions] of Object.entries(this.lexicon.aliases)) this.phrases.set(tokenize(term).join(' '), expansions);
    this.glossary = new Map();
    for (const [term, definition] of Object.entries(this.lexicon.glossary)) this.glossary.set(tokenize(term).join(' '), { term, definition });
  }

  get size() { return this.docs.length; }

  /** Add compact docs ({i,k,t,s,c,e,o,n,d,u,x}). A doc id already present is skipped. */
  add(docs) {
    for (const doc of docs || []) {
      if (!doc || this.ids.has(doc.i)) continue;
      this.ids.add(doc.i);
      if (doc.c) this.sections.add(doc.c);
      const index = this.docs.push(doc) - 1;
      const tf = new Map();
      const bump = (token, weight) => tf.set(token, (tf.get(token) || 0) + weight);
      for (const token of stems(doc.t)) bump(token, FIELD_WEIGHT.title);
      for (const token of stems(doc.s)) bump(token, FIELD_WEIGHT.summary);
      for (const token of stems(doc.o)) bump(token, FIELD_WEIGHT.source);
      for (const id of doc.e || []) {
        bump(`@${id}`, FIELD_WEIGHT.entity);
        const entity = this.lexicon.entities[id];
        if (entity) for (const token of stems(entity.name)) bump(token, FIELD_WEIGHT.entity);
      }
      let length = 0;
      for (const [token, weight] of tf) {
        length += weight;
        let posting = this.postings.get(token);
        if (!posting) this.postings.set(token, (posting = new Map()));
        posting.set(index, weight);
      }
      this.lengths.push(length);
      this.totalLength += length;
    }
  }

  /** BM25 score of one stem for every doc that has it. */
  scoreStem(token) {
    const posting = this.postings.get(token);
    const scores = new Map();
    if (!posting) return scores;
    const n = this.docs.length;
    const average = this.totalLength / Math.max(1, n);
    const idf = Math.log(1 + (n - posting.size + 0.5) / (posting.size + 0.5));
    for (const [index, tf] of posting) {
      scores.set(index, (idf * tf * (K1 + 1)) / (tf + K1 * (1 - B + (B * this.lengths[index]) / average)));
    }
    return scores;
  }

  /** Docs containing every stem of a phrase; score is the sum. With `exact`, the words must be adjacent in the text. */
  scoreAll(tokens, exact = null) {
    if (!tokens.length) return new Map();
    const maps = tokens.map((token) => this.scoreStem(token)).sort((a, b) => a.size - b.size);
    const out = new Map();
    for (const [index, score] of maps[0]) {
      let total = score;
      let ok = true;
      for (let i = 1; i < maps.length; i++) {
        const other = maps[i].get(index);
        if (other === undefined) { ok = false; break; }
        total += other;
      }
      if (ok && exact) {
        const doc = this.docs[index];
        ok = ` ${tokenize(`${doc.t} . ${doc.s || ''}`).join(' ')}`.includes(` ${exact}`); // from a word boundary: "rate cut" is not in "pirate cut"
      }
      if (ok) out.set(index, total);
    }
    return out;
  }

  /** Ways one query word could match, widest last. Each alt: {kind, label, key, tokens|entity, weight}. */
  alternatives(word, { isLast, typing, exactOnly }) {
    const tokens = tokenize(word.text);
    const phrase = tokens.join(' ');
    const alts = [];
    if (!tokens.length) return alts;
    const stemmed = tokens.map(stem);
    alts.push({ kind: 'direct', label: word.text, key: `direct:${phrase}`, tokens: stemmed, weight: WEIGHT.direct, exact: word.phrase && tokens.length > 1 ? phrase : null });
    if (exactOnly || word.phrase) return alts;

    const entityId = this.surface.get(phrase);
    if (entityId) {
      const entity = this.lexicon.entities[entityId];
      alts.push({ kind: 'entity', label: entity.name, key: `entity:${entityId}`, entity: entityId, weight: WEIGHT.entity, quiet: true });
      for (const related of entity.related || []) {
        const other = this.lexicon.entities[related];
        if (other) alts.push({ kind: 'relatedEntity', label: other.name, key: `entity:${related}`, entity: related, weight: WEIGHT.relatedEntity });
      }
      for (const alias of entity.aliases || []) {
        const aliasTokens = tokenize(alias);
        if (aliasTokens.join(' ') !== phrase && aliasTokens.length) {
          alts.push({ kind: 'alias', label: alias, key: `alias:${aliasTokens.join(' ')}`, tokens: aliasTokens.map(stem), weight: WEIGHT.alias, exact: aliasTokens.length > 1 ? aliasTokens.join(' ') : null });
        }
      }
      if (entity.name && tokenize(entity.name).join(' ') !== phrase) {
        const nameTokens = tokenize(entity.name);
        alts.push({ kind: 'alias', label: entity.name, key: `alias:${nameTokens.join(' ')}`, tokens: nameTokens.map(stem), weight: WEIGHT.alias, exact: nameTokens.length > 1 ? nameTokens.join(' ') : null, quiet: true });
      }
    }
    for (const expansion of this.phrases.get(phrase) || []) {
      const expansionTokens = tokenize(expansion);
      if (expansionTokens.length) alts.push({ kind: 'alias', label: expansion, key: `alias:${expansionTokens.join(' ')}`, tokens: expansionTokens.map(stem), weight: WEIGHT.alias, exact: expansionTokens.length > 1 ? expansionTokens.join(' ') : null });
    }
    if (tokens.length === 1) {
      const token = stemmed[0];
      for (const [neighbour, weight] of (this.lexicon.related[token] || []).slice(0, 4)) { // the four strongest; more only adds noise
        const label = neighbour.startsWith('@') ? this.lexicon.entities[neighbour.slice(1)]?.name || neighbour.slice(1) : neighbour;
        alts.push({ kind: 'related', label, key: `related:${neighbour}`, tokens: [neighbour], weight: WEIGHT.related * Math.max(0.3, Math.min(1, weight)) });
      }
      const known = this.postings.has(token);
      if ((typing && isLast && token.length >= 2) || (!known && token.length >= 3)) {
        const matches = [];
        for (const [candidate, posting] of this.postings) {
          if (candidate !== token && candidate.startsWith(token) && !candidate.startsWith('@')) matches.push([candidate, posting.size]);
        }
        matches.sort((a, b) => b[1] - a[1]);
        for (const [candidate] of matches.slice(0, 12)) alts.push({ kind: 'prefix', label: candidate, key: `prefix:${candidate}`, tokens: [candidate], weight: WEIGHT.prefix, quiet: typing && isLast });
      }
      if (!known && token.length >= 5 && !DIGIT.test(token)) {
        const max = token.length >= 9 ? 2 : 1;
        const near = [];
        for (const [candidate, posting] of this.postings) {
          if (candidate.startsWith('@') || candidate[0] !== token[0]) continue;
          const distance = editDistance(token, candidate, max);
          if (distance <= max) near.push([candidate, distance, posting.size]);
        }
        near.sort((a, b) => a[1] - b[1] || b[2] - a[2]);
        for (const [candidate] of near.slice(0, 3)) alts.push({ kind: 'fuzzy', label: candidate, key: `fuzzy:${candidate}`, tokens: [candidate], weight: WEIGHT.fuzzy });
      }
    }
    return alts;
  }

  /**
   * Group adjacent query words that together name an entity or a known phrase
   * ("jensen huang", "rate cut"), so they expand as one unit.
   */
  group(words) {
    const out = [];
    for (let i = 0; i < words.length;) {
      let taken = 0;
      if (!words[i].phrase && !words[i].negate) {
        for (let size = Math.min(4, words.length - i); size >= 2; size--) {
          const slice = words.slice(i, i + size);
          if (slice.some((w) => w.phrase || w.negate)) continue;
          const key = tokenize(slice.map((w) => w.text).join(' ')).join(' ');
          if (this.surface.has(key) || this.phrases.has(key)) {
            out.push({ text: slice.map((w) => w.text).join(' '), phrase: false, negate: false, joined: true });
            taken = size;
            break;
          }
        }
      }
      if (!taken) { out.push(words[i]); taken = 1; }
      i += taken;
    }
    return out;
  }

  /**
   * opts: limit, offset, sort 'relevance'|'newest', exactOnly, drop (expansion keys the reader removed),
   * typing (last word may be incomplete), kinds, now (ms), predicate(doc).
   */
  search(query, opts = {}) {
    const started = typeof performance !== 'undefined' ? performance.now() : 0;
    const { limit = 50, offset = 0, sort = 'relevance', exactOnly = false, drop = [], typing = false, now = Date.now() } = opts;
    const parsed = parseQuery(query);
    const dropped = new Set(drop);
    let words = this.group(parsed.words);
    const content = words.filter((w) => w.phrase || tokenize(w.text).some((t) => !STOPWORDS.has(t)));
    if (content.length) words = content; // "the fed" keeps "fed"; a query of only stopwords is kept as typed

    const positive = [];
    const negative = [];
    const expansions = new Map();
    const marks = new Set();
    let didYouMean = null;

    words.forEach((word, position) => {
      const alts = this.alternatives(word, { isLast: position === words.length - 1, typing, exactOnly });
      if (word.negate) {
        negative.push(this.scoreAll(alts[0]?.tokens || [], alts[0]?.exact));
        return;
      }
      const scores = new Map(); // doc -> {score, via}
      let directHits = 0;
      for (const alt of alts) {
        if (alt.kind !== 'direct' && dropped.has(alt.key)) continue;
        const found = alt.entity ? this.scoreStem(`@${alt.entity}`) : this.scoreAll(alt.tokens, alt.exact);
        if (!found.size) continue;
        if (alt.kind === 'direct') directHits = found.size;
        if (alt.kind === 'fuzzy' && !directHits && !didYouMean) didYouMean = alt.label;
        if (alt.kind !== 'direct' && !alt.quiet && !expansions.has(alt.key)) expansions.set(alt.key, { key: alt.key, label: alt.label, kind: alt.kind, from: word.text, count: found.size });
        for (const token of alt.tokens || []) marks.add(token);
        if (alt.entity) for (const token of stems(this.lexicon.entities[alt.entity]?.name || '')) marks.add(token);
        for (const [index, value] of found) {
          const weighted = value * alt.weight;
          const existing = scores.get(index);
          if (!existing || weighted > existing.score) scores.set(index, { score: weighted, via: alt.kind === 'direct' || alt.quiet ? null : alt.label });
        }
      }
      positive.push(scores);
    });

    const pass = (doc) => this.passes(doc, parsed.filters, opts);
    const collect = (requireAll) => {
      const totals = new Map();
      if (!positive.length) return totals;
      const base = requireAll ? [...positive].sort((a, b) => a.size - b.size)[0] : null;
      const candidates = requireAll ? base.keys() : new Set(positive.flatMap((m) => [...m.keys()]));
      for (const index of candidates) {
        let total = 0;
        let matched = 0;
        const via = [];
        for (const scores of positive) {
          const hit = scores.get(index);
          if (hit) { total += hit.score; matched++; if (hit.via) via.push(hit.via); }
        }
        if (requireAll && matched < positive.length) continue;
        if (negative.some((scores) => scores.has(index))) continue;
        const doc = this.docs[index];
        if (!pass(doc)) continue;
        totals.set(index, { score: total * (requireAll ? 1 : matched / positive.length), via });
      }
      return totals;
    };

    let partial = false;
    let totals;
    if (positive.length) {
      totals = collect(true);
      if (!totals.size && positive.length > 1) { totals = collect(false); partial = totals.size > 0; }
    } else {
      // filters only ("desk:ai is:saved"): everything that passes, newest first
      totals = new Map();
      this.docs.forEach((doc, index) => { if (pass(doc) && !negative.some((scores) => scores.has(index))) totals.set(index, { score: 1, via: [] }); });
    }

    const hits = [];
    const counts = {};
    for (const [index, { score, via }] of totals) {
      const doc = this.docs[index];
      counts[doc.k] = (counts[doc.k] || 0) + 1;
      const age = doc.d ? Math.max(0, (now - Date.parse(doc.d)) / 86400000) : null;
      const recency = age === null ? 0.9 : 0.6 + 0.4 * Math.pow(0.5, age / 21);
      const coverage = 1 + 0.08 * Math.log2(Math.max(1, doc.n || 1));
      hits.push({ doc, score: score * recency * coverage, via });
    }
    if (sort === 'newest' || !positive.length) hits.sort((a, b) => (b.doc.d || '').localeCompare(a.doc.d || '') || b.score - a.score);
    else hits.sort((a, b) => b.score - a.score || (b.doc.d || '').localeCompare(a.doc.d || ''));

    const phrase = tokenize(words.filter((w) => !w.negate).map((w) => w.text).join(' ')).join(' ');
    const entityId = this.surface.get(phrase);
    return {
      total: hits.length,
      hits: hits.slice(offset, offset + limit),
      expansions: [...expansions.values()],
      marks: [...marks],
      counts,
      partial,
      didYouMean: didYouMean && !hits.length ? didYouMean : (didYouMean && hits.length < 3 ? didYouMean : null),
      definition: this.glossary.get(phrase) || null,
      entity: entityId ? { id: entityId, ...this.lexicon.entities[entityId] } : null,
      filters: parsed.filters,
      ms: typeof performance !== 'undefined' ? Math.round(performance.now() - started) : 0,
    };
  }

  passes(doc, filters, opts) {
    const kinds = opts.kinds || filters.kinds;
    if (kinds && !kinds.includes(doc.k)) return false;
    if (filters.section && doc.c !== filters.section && (this.sections.has(filters.section) || !String(doc.c || '').startsWith(filters.section))) return false;
    if (filters.source && !String(doc.o || '').toLowerCase().includes(filters.source)) return false;
    // the reader types dates in the paper's calendar, so compare against the day in the paper's timezone
    if (filters.after && (!doc.d || localDay(doc.d, opts.timeZone) < filters.after)) return false;
    if (filters.before && (!doc.d || localDay(doc.d, opts.timeZone) > filters.before)) return false;
    if (opts.predicate && !opts.predicate(doc, filters)) return false;
    return true;
  }
}

/** Split text into pieces for highlighting: [{text, mark}], marking words whose stem is in `marks`. */
export function highlight(text, marks) {
  const wanted = marks instanceof Set ? marks : new Set(marks);
  const out = [];
  let last = 0;
  const source = String(text ?? '');
  for (const match of source.matchAll(/[A-Za-z0-9À-ɏ]+(?:[&.\-'’][A-Za-z0-9À-ɏ]+)*\+*/g)) {
    const tokens = tokenize(match[0]);
    if (!tokens.some((token) => wanted.has(stem(token)) || wanted.has(token))) continue;
    if (match.index > last) out.push({ text: source.slice(last, match.index), mark: false });
    out.push({ text: match[0], mark: true });
    last = match.index + match[0].length;
  }
  if (last < source.length) out.push({ text: source.slice(last), mark: false });
  return out;
}
