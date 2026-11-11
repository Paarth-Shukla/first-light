// Search worker: downloads the doc shards and the lexicon, builds the index off the main thread, answers queries.
// Protocol: {id, type: 'search', query, opts} -> {id, result}. It also posts {type: 'state', ...} as shards arrive.

import { SearchIndex } from './engine.js';

const BASE = new URL('../../data/search/', import.meta.url);
let index = null;
let state = { ready: false, docs: 0, loaded: [], pending: [], error: null };
const waiting = [];

const getJSON = async (name) => {
  const response = await fetch(new URL(name, BASE), { cache: 'no-cache' });
  if (!response.ok) throw new Error(`${name}: ${response.status}`);
  return response.json();
};

function announce() {
  state.docs = index ? index.size : 0;
  postMessage({ type: 'state', state: { ...state } });
}

async function boot() {
  try {
    const [manifest, lexicon] = await Promise.all([getJSON('manifest.json'), getJSON('lexicon.json').catch(() => ({}))]);
    index = new SearchIndex(lexicon);
    const shards = [...(manifest.shards || [])].sort((a, b) => b.month.localeCompare(a.month));
    state.pending = shards.map((shard) => shard.month);
    const first = shards.slice(0, 2);
    const staticDocs = manifest.static ? getJSON(manifest.static).catch(() => []) : Promise.resolve([]);
    const loaded = await Promise.all([staticDocs, ...first.map((shard) => getJSON(shard.file).catch(() => []))]);
    for (const docs of loaded) index.add(docs);
    state.loaded = first.map((shard) => shard.month);
    state.pending = shards.slice(2).map((shard) => shard.month);
    state.ready = true;
    announce();
    for (const job of waiting.splice(0)) answer(job);
    for (const shard of shards.slice(2)) { // older months arrive in the background, newest first
      try { index.add(await getJSON(shard.file)); } catch { /* a missing month only narrows the archive */ }
      state.loaded.push(shard.month);
      state.pending = state.pending.filter((month) => month !== shard.month);
      announce();
    }
  } catch (error) {
    state.error = String(error.message || error);
    state.ready = true;
    if (!index) index = new SearchIndex({});
    announce();
    for (const job of waiting.splice(0)) answer(job);
  }
}

function answer({ id, query, opts }) {
  const saved = opts?.savedIds ? new Set(opts.savedIds) : null;
  const read = opts?.readIds ? new Set(opts.readIds) : null;
  const predicate = (doc, filters) => {
    if (filters.is?.includes('saved') && saved && !saved.has(doc.i)) return false;
    if (filters.is?.includes('unread') && read && read.has(doc.i)) return false;
    return true;
  };
  postMessage({ id, result: index.search(query, { ...opts, predicate }), state: { ...state, docs: index.size } });
}

onmessage = (event) => {
  const job = event.data;
  if (job.type !== 'search') return;
  if (state.ready) answer(job);
  else waiting.push(job);
};

boot();
