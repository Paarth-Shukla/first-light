// Everything personal lives here, in this browser only: localStorage under the "fl." prefix.

const PREFIX = 'fl.';
const listeners = new Map();
const memory = new Map(); // fallback when localStorage is unavailable (private mode, blocked) or full
const fullListeners = new Set();
let warnedFull = false;

/** Called once, the first time a write cannot be kept. */
export function onStorageFull(fn) { fullListeners.add(fn); }

function raw(key) {
  // a value that could not be written (storage full or blocked) lives in memory and wins for this session
  if (memory.has(key)) return memory.get(key);
  try {
    return localStorage.getItem(PREFIX + key);
  } catch {
    return null;
  }
}

const isMap = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);

/** Read a stored value. A missing, corrupt, null or wrong-shaped value reads as the fallback, never as garbage. */
export function get(key, fallback) {
  const text = raw(key);
  if (text === null) return fallback;
  try {
    const value = JSON.parse(text);
    if (value === null || value === undefined) return fallback;
    if (isMap(fallback) && !isMap(value)) return fallback;
    if (Array.isArray(fallback) && !Array.isArray(value)) return fallback;
    return value;
  } catch {
    return fallback;
  }
}

export function set(key, value) {
  const text = JSON.stringify(value);
  try {
    localStorage.setItem(PREFIX + key, text);
    memory.delete(key);
  } catch {
    memory.set(key, text);
    if (!warnedFull) { warnedFull = true; for (const fn of fullListeners) fn(); }
  }
  for (const fn of listeners.get(key) || []) fn(value);
}

export function update(key, fallback, fn) {
  const next = fn(get(key, fallback));
  set(key, next);
  return next;
}

export function subscribe(key, fn) {
  if (!listeners.has(key)) listeners.set(key, new Set());
  listeners.get(key).add(fn);
  return () => listeners.get(key).delete(fn);
}

// ---- reading state -------------------------------------------------------

const READ_KEEP_DAYS = 60;

export function isRead(id) {
  return Boolean(get('read', {})[id]);
}

export function markRead(id, read = true) {
  update('read', {}, (map) => {
    if (read) map[id] = Date.now();
    else delete map[id];
    return map;
  });
}

/** Drop read marks older than the retention window so the map never grows without bound. */
export function pruneRead() {
  const cutoff = Date.now() - READ_KEEP_DAYS * 86400000;
  update('read', {}, (map) => Object.fromEntries(Object.entries(map).filter(([, at]) => at >= cutoff)));
}

// ---- clippings -----------------------------------------------------------
// A clipping keeps a snapshot of the item, so it survives the 90-day data window.

export function clippings() {
  return get('saved', {});
}

export function isClipped(key) {
  return Boolean(clippings()[key]);
}

export function clip(key, snapshot) {
  update('saved', {}, (map) => ({ ...map, [key]: { ...snapshot, savedAt: Date.now(), note: map[key]?.note || '' } }));
}

export function unclip(key) {
  update('saved', {}, (map) => {
    delete map[key];
    return map;
  });
}

export function toggleClip(key, snapshot) {
  if (isClipped(key)) { unclip(key); return false; }
  clip(key, snapshot);
  return true;
}

export function setNote(key, note) {
  update('saved', {}, (map) => {
    if (map[key]) map[key].note = note;
    return map;
  });
}

// ---- export / import -----------------------------------------------------

const KEYS = ['read', 'saved', 'prefs', 'visit', 'claude', 'search', 'seen'];

export function exportAll() {
  const out = { app: 'first-light', version: 1, exportedAt: new Date().toISOString(), data: {} };
  for (const key of KEYS) {
    const value = get(key, undefined);
    if (value !== undefined) out.data[key] = value;
  }
  return out;
}

/**
 * Merge an exported file into this browser. Every key is a map; entries from the file are added to
 * what is here, and where both have an entry the file's wins. Anything that is not a map is ignored,
 * so a damaged file cannot leave the site unable to start.
 */
export function importAll(file) {
  if (!isMap(file) || file.app !== 'first-light' || !isMap(file.data)) throw new Error('Not a First Light export file.');
  let imported = 0;
  for (const key of KEYS) {
    const incoming = file.data[key];
    if (!isMap(incoming)) continue;
    set(key, { ...get(key, {}), ...incoming });
    imported++;
  }
  if (!imported) throw new Error('That file holds nothing to import.');
}

export function clearAll() {
  for (const key of KEYS) {
    try { localStorage.removeItem(PREFIX + key); } catch { /* nothing to clear */ }
    memory.delete(key);
    for (const fn of listeners.get(key) || []) fn(undefined);
  }
}
