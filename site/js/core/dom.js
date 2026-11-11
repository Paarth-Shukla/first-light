// DOM helpers. Remote text only ever enters the page through text nodes built here.

const SVG_NS = 'http://www.w3.org/2000/svg';

/** Append children (strings become text nodes; null/false are skipped; arrays are flattened). */
export function append(el, ...children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false || child === '') continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

/**
 * Create an element: h('a.more.label', {href: '#/wire', onclick: fn}, 'text', childNode).
 * The tag may carry classes and an id (`div#x.a.b`). Attribute values of null/false are skipped.
 */
export function h(spec, attrs, ...children) {
  if (attrs instanceof Node || typeof attrs === 'string' || Array.isArray(attrs)) {
    children.unshift(attrs);
    attrs = null;
  }
  // the id may sit anywhere in the spec: 'h2#x.title' and 'h2.title#x' both work
  const id = /#([\w-]+)/.exec(spec)?.[1];
  const [tag, ...classes] = spec.replace(/#[\w-]+/, '').split('.');
  const el = document.createElement(tag || 'div');
  if (id) el.id = id;
  if (classes.length) el.className = classes.join(' ');
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') el.className = `${el.className} ${value}`.trim();
    else if (key === 'style' && typeof value === 'object') Object.assign(el.style, value);
    else if (key === 'dataset') Object.assign(el.dataset, value);
    else if (key.startsWith('on') && typeof value === 'function') el.addEventListener(key.slice(2), value);
    else if (value === true) el.setAttribute(key, '');
    else el.setAttribute(key, String(value));
  }
  return append(el, children);
}

/** An icon from the sprite in index.html: arw('ne'), arw('up'), arw('copy'), arw('find'). */
export function arw(kind, extra = '') {
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('class', `arw ${extra}`.trim());
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('focusable', 'false');
  const use = document.createElementNS(SVG_NS, 'use');
  use.setAttribute('href', `#a-${kind}`);
  svg.append(use);
  return svg;
}

/** Build an SVG element tree: s('polyline', {points: '…'}). */
export function s(tag, attrs, ...children) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value !== null && value !== undefined && value !== false) el.setAttribute(key, String(value));
  }
  return append(el, children);
}

export function clear(el) {
  el.replaceChildren();
  return el;
}

export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

/** Links that leave the site: new tab, no opener, no referrer. */
export function outLink(url, attrs, ...children) {
  return h('a', { href: safeUrl(url), target: '_blank', rel: 'noopener noreferrer', ...attrs }, children);
}

/** Only http(s) and in-app hash links are ever put in an href. */
export function safeUrl(url) {
  if (typeof url !== 'string') return '#/';
  if (url.startsWith('#/')) return url;
  try {
    const parsed = new URL(url, location.href);
    return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? parsed.href : '#/';
  } catch {
    return '#/';
  }
}

const ALLOWED_TAGS = new Set(['H2', 'H3', 'H4', 'P', 'UL', 'OL', 'LI', 'PRE', 'CODE', 'STRONG', 'EM', 'A', 'BLOCKQUOTE', 'HR', 'BR']);

/**
 * Render HTML produced by our own playbook compiler. It is already escaped at build time;
 * this walk is a second lock: unknown tags are unwrapped, attributes are dropped, links are checked.
 */
export function trustedHtml(html) {
  const doc = new DOMParser().parseFromString(`<div>${html || ''}</div>`, 'text/html');
  const out = document.createDocumentFragment();
  const copy = (node, into) => {
    for (const child of node.childNodes) {
      if (child.nodeType === Node.TEXT_NODE) {
        into.append(child.textContent);
      } else if (child.nodeType === Node.ELEMENT_NODE) {
        if (child.tagName === 'SCRIPT' || child.tagName === 'STYLE') continue;
        if (!ALLOWED_TAGS.has(child.tagName)) { copy(child, into); continue; }
        const el = document.createElement(child.tagName);
        if (child.tagName === 'A') {
          el.href = safeUrl(child.getAttribute('href'));
          if (!el.getAttribute('href').startsWith('#/')) { el.target = '_blank'; el.rel = 'noopener noreferrer'; }
        }
        if (child.tagName === 'CODE' && /^language-[a-z0-9]+$/.test(child.className)) el.className = child.className;
        copy(child, el);
        into.append(el);
      }
    }
  };
  copy(doc.body.firstChild, out);
  return out;
}

/** Copy text; resolves true when the clipboard accepted it. */
export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const area = h('textarea', { style: { position: 'fixed', opacity: '0' } });
    area.value = text;
    document.body.append(area);
    area.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch { ok = false; }
    area.remove();
    return ok;
  }
}
