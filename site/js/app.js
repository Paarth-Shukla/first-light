// Boot: load the manifest, set up the shell, register the routes, start the router.
// A module is {id, routes: [[path, view]]}; adding a non-news module later means adding one entry to MODULES.

import { h, $ } from './core/dom.js';
import * as data from './core/data.js';
import * as store from './core/store.js';
import { route, start } from './core/router.js';
import { setZone } from './core/time.js';
import { setDesks, notice } from './core/ui.js';
import * as shell from './shell.js';
import { frontView } from './views/front.js';
import { wireView, deskView } from './views/wire.js';
import { storyView } from './views/story.js';
import { marketsView } from './views/markets.js';
import { weekendView } from './views/weekend.js';
import { claudeHome, claudeUpdates, claudePlaybook, claudeFeature, claudeRecipes, claudeRecipe } from './views/claude.js';
import { searchView } from './views/search.js';
import { clippingsView, archiveView, settingsView, colophonView } from './views/pages.js';

const MODULES = [
  { id: 'news', routes: [['/', frontView], ['/edition/:date', frontView], ['/wire', wireView], ['/s/:section', deskView], ['/story/:id', storyView], ['/archive', archiveView]] },
  { id: 'markets', routes: [['/markets', marketsView]] },
  { id: 'weekend', routes: [['/weekend', weekendView], ['/weekend/:week', weekendView]] },
  { id: 'claude', routes: [['/claude', claudeHome], ['/claude/updates', claudeUpdates], ['/claude/playbook', claudePlaybook], ['/claude/feature/:id', claudeFeature], ['/claude/recipes', claudeRecipes], ['/claude/recipe/:id', claudeRecipe]] },
  { id: 'search', routes: [['/search', searchView]] },
  { id: 'reader', routes: [['/clippings', clippingsView], ['/settings', settingsView], ['/colophon', colophonView]] },
];

function notFound(el, params, ctx) {
  ctx.setPage({ title: 'No such page', kicker: 'First Light' });
  el.append(h('div.wrap.page', notice('There is no page at this address.', null, h('a.readon', { href: '#/' }, 'Go to the Front Page'))));
}

async function boot() {
  const view = $('#view');
  let manifest;
  try {
    manifest = await data.manifest();
  } catch (error) {
    // No data at all: the site was opened before the pipeline ever ran.
    setDesks([]);
    shell.init(null);
    shell.setPage({ title: 'Nothing has been built yet', kicker: 'First Light' });
    view.replaceChildren(h('div.wrap.page', notice('There is no edition to show.',
      'The pipeline has not produced any data. In the repository, run “python3 -m pipeline all”, then reload this page.')));
    console.error(error);
    return;
  }
  setZone(manifest.site?.timezone);
  setDesks(manifest.sections);
  store.pruneRead();
  shell.init(manifest);
  for (const module of MODULES) for (const [path, viewFn] of module.routes) route(path, viewFn);
  route('*', notFound);
  let firstRender = true;
  await start(view, {
    // what a view may do to the shell, valid only while its render is the current one
    context: (alive) => ({
      setPage: (page) => { if (alive()) shell.setPage(page); },
      setFrontPlate: (front) => { if (alive()) shell.setFrontPlate(front); },
      setViewKeys: (keys) => { if (alive()) shell.setViewKeys(keys); },
    }),
    error: (el, error, ctx) => {
      ctx.setPage({ title: 'This page could not be set', kicker: 'First Light' });
      el.replaceChildren(h('div.wrap.page', notice('This page could not be set.', error?.message || 'Something went wrong while loading it.',
        h('button.readon', { type: 'button', onclick: () => location.reload() }, 'Try again'))));
    },
    // after a navigation, focus moves to the new page; on first load it stays put so Tab reaches the skip link first
    after: () => { if (!firstRender && document.activeElement === document.body) view.focus({ preventScroll: true }); firstRender = false; },
  });
  if ('serviceWorker' in navigator && location.protocol === 'https:') {
    navigator.serviceWorker.register('sw.js').catch(() => { /* offline reading is a nicety, not a requirement */ });
  }
}

boot();
