// Main-thread side of search: one shared worker, promise API, and a notification when more of the archive arrives.

import * as store from '../core/store.js';
import { zoneId } from '../core/time.js';

let worker = null;
let nextId = 1;
const pending = new Map();
const stateListeners = new Set();
let lastState = { ready: false, docs: 0, loaded: [], pending: [], error: null };

function ensureWorker() {
  if (worker) return worker;
  worker = new Worker(new URL('./worker.js', import.meta.url), { type: 'module' });
  worker.onmessage = (event) => {
    const message = event.data;
    if (message.state) {
      lastState = message.state;
      // only the worker's own progress messages notify listeners; a reply to a query must not trigger another query
      if (message.type === 'state') for (const fn of stateListeners) fn(lastState);
    }
    if (message.id && pending.has(message.id)) {
      pending.get(message.id)(message.result);
      pending.delete(message.id);
    }
  };
  worker.onerror = (event) => {
    lastState = { ...lastState, ready: true, error: event.message || 'Search could not start.' };
    for (const fn of stateListeners) fn(lastState);
    for (const resolve of pending.values()) resolve(null);
    pending.clear();
  };
  return worker;
}

/** Start loading the index before the reader types (called when a search field gets focus). */
export function warm() {
  ensureWorker();
}

/** Run a query. Resolves to the engine's result, or null when search is unavailable. */
export function search(query, opts = {}) {
  const id = nextId++;
  // Story and paper docs share their id with the clipping; technique and recipe docs are
  // "feature:<id>" / "recipe:<id>", which is the clipping's key.
  const savedIds = Object.entries(store.clippings()).flatMap(([key, item]) => [item.id, key]);
  const readIds = Object.keys(store.get('read', {}));
  return new Promise((resolve) => {
    pending.set(id, resolve);
    ensureWorker().postMessage({ id, type: 'search', query, opts: { ...opts, savedIds, readIds, timeZone: zoneId() } });
  });
}

export function onState(fn) {
  stateListeners.add(fn);
  fn(lastState);
  return () => stateListeners.delete(fn);
}

export const state = () => lastState;
