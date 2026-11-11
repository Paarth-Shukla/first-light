// Loads the JSON the pipeline publishes under data/. Paths are relative, so the site works under any base path.

const cache = new Map();

export class DataError extends Error {
  constructor(path, status) {
    super(status === 404 ? `Not published yet: ${path}` : `Could not load ${path} (${status || 'network'})`);
    this.path = path;
    this.status = status;
  }
}

/** Fetch data/<path> once per page load. Concurrent callers share one request. */
export function load(path) {
  if (!cache.has(path)) {
    const request = fetch(`data/${path}`, { cache: 'no-cache' })
      .then((response) => {
        if (!response.ok) throw new DataError(path, response.status);
        return response.json();
      })
      .catch((error) => {
        cache.delete(path); // let a later navigation retry
        throw error instanceof DataError ? error : new DataError(path, 0);
      });
    cache.set(path, request);
  }
  return cache.get(path);
}

/** Like load(), but resolves to `fallback` when the file is missing or unreachable. */
export function loadOr(path, fallback) {
  return load(path).catch(() => fallback);
}

export const isDay = (value) => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value);
export const isWeek = (value) => typeof value === 'string' && /^\d{4}-W\d{2}$/.test(value);

export const manifest = () => load('manifest.json');
export const latest = () => load('latest.json');
export const markets = () => loadOr('markets.json', null);
export const playbook = () => loadOr('claude/playbook.json', { features: [], recipes: [], surfaces: [], jobs: [] });
export const updates = () => loadOr('claude/updates.json', { entries: [], status: null });
export const edition = (date) => load(`editions/${date}.json`);
export const day = (date) => load(`stories/${date}.json`);

/** Find one story by id: the hot set first, then the given day, then recent days. */
export async function findStory(id, dayHint) {
  const hot = await loadOr('latest.json', { stories: [] });
  let story = hot.stories.find((item) => item.id === id);
  if (story) return story;
  const days = isDay(dayHint) ? [dayHint] : [];
  const info = await loadOr('manifest.json', { days: [] });
  const known = [...(info.days || [])].filter(isDay).sort().reverse(); // newest first
  // a story is filed under the day it was first reported, which can be a few days before the hint
  for (const date of known) if (!days.includes(date) && (!days.length || date <= days[0])) days.push(date);
  for (const date of known) if (!days.includes(date)) days.push(date);
  for (const date of days.slice(0, 21)) {
    const file = await loadOr(`stories/${date}.json`, null);
    story = file?.stories?.find((item) => item.id === id);
    if (story) return story;
  }
  return null;
}
