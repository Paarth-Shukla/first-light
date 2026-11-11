// A tiny test runner for the browser. Exposes window.__tests = {done, passed, failed, results: [{name, ok, error}]}.

const results = [];
const tests = [];
window.__tests = { done: false, passed: 0, failed: 0, results };

export function test(name, fn) { tests.push({ name, fn }); }

export function equal(actual, expected, message = '') {
  const a = JSON.stringify(actual);
  const b = JSON.stringify(expected);
  if (a !== b) throw new Error(`${message} expected ${b} but got ${a}`.trim());
}

export function ok(value, message = 'expected a truthy value') {
  if (!value) throw new Error(message);
}

async function main() {
  await import('./engine.test.js');
  const out = document.getElementById('out');
  for (const { name, fn } of tests) {
    let error = null;
    try { await fn(); } catch (caught) { error = String(caught && caught.message ? caught.message : caught); }
    results.push({ name, ok: !error, error });
    const item = document.createElement('li');
    item.className = error ? 'bad' : 'ok';
    item.textContent = error ? `FAIL ${name}: ${error}` : `ok ${name}`;
    out.append(item);
  }
  window.__tests.passed = results.filter((r) => r.ok).length;
  window.__tests.failed = results.length - window.__tests.passed;
  window.__tests.done = true;
  document.title = `${window.__tests.failed ? 'FAIL' : 'PASS'} · ${window.__tests.passed}/${results.length}`;
}

main().catch((error) => {
  results.push({ name: 'test runner', ok: false, error: String(error && error.stack ? error.stack : error) });
  window.__tests.failed = 1;
  window.__tests.done = true;
});
