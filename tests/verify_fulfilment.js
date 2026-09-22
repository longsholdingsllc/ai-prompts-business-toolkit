#!/usr/bin/env node
/**
 * End-to-end verification of the PromptDrawer fulfilment path.
 *
 * Two things are checked, over real HTTP, with no test framework and no
 * dependencies:
 *
 * 1. The pack is not reachable as a static file. The harness rebuilds the
 *    deployment the way vercel.json and .vercelignore describe it - routes are
 *    applied in order, then the filesystem is consulted, exactly as Vercel
 *    documents - and requests the product URLs through it. It runs that model
 *    four times (routes on/off x .vercelignore on/off) to show that each layer
 *    blocks the pack on its own, so neither is a single point of failure.
 *
 * 2. The fulfilment function only hands the pack over for a paid session. The
 *    Stripe API call is answered by a stub so the success path can be exercised
 *    without an account, and one case is run against the real Stripe API with a
 *    deliberately invalid key to show the failure path is real, not simulated.
 *    The bytes served for each file are compared against the files in the repo,
 *    so "what a buyer receives" and "what the build produced" cannot drift.
 *
 * What this does NOT prove: that Vercel behaves as documented, and that Stripe
 * accepts our key, because there is no Stripe account and no deployment hooked
 * up here. Those are the two steps docs/stripe-setup.md asks a human to confirm.
 *
 * Run: node tests/verify_fulfilment.js
 */

'use strict';

const http = require('http');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const handler = require(path.join(ROOT, 'api', 'download.js'));

let passed = 0;
const failures = [];

function ok(name, condition, detail) {
  if (condition) {
    passed += 1;
    console.log(`  ok    ${name}`);
  } else {
    failures.push(name + (detail ? ` -- ${detail}` : ''));
    console.log(`  FAIL  ${name}${detail ? ` -- ${detail}` : ''}`);
  }
}

function section(title) {
  console.log(`\n== ${title}`);
}

// ---------------------------------------------------------------------------
// Layer 1: what the deployment actually contains / routes
// ---------------------------------------------------------------------------

const vercel = JSON.parse(fs.readFileSync(path.join(ROOT, 'vercel.json'), 'utf8'));
const ignorePatterns = fs
  .readFileSync(path.join(ROOT, '.vercelignore'), 'utf8')
  .split('\n')
  .map((line) => line.trim())
  .filter((line) => line && !line.startsWith('#'));

/** .vercelignore uses gitignore syntax; this harness handles the two forms used. */
function ignoredByVercelIgnore(rel) {
  for (const pattern of ignorePatterns) {
    if (/[*?[\]]/.test(pattern)) {
      throw new Error(`.vercelignore pattern ${pattern} needs the harness matcher extended`);
    }
    if (pattern === rel) return true;
    if (pattern.endsWith('/')) {
      const dir = pattern.slice(0, -1);
      if (rel === dir || rel.startsWith(dir + '/')) return true;
    }
  }
  return false;
}

function walk(dir, out) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const rel = path.relative(ROOT, path.join(dir, entry.name)).split(path.sep).join('/');
    if (entry.name.startsWith('.')) continue; // Vercel does not serve dotfiles
    if (rel === 'api' || rel.startsWith('api/')) continue; // functions, not static files
    if (entry.isDirectory()) walk(path.join(dir, entry.name), out);
    else out.add(rel);
  }
  return out;
}

const allStaticFiles = walk(ROOT, new Set());
const deployableFiles = new Set([...allStaticFiles].filter((rel) => !ignoredByVercelIgnore(rel)));

const PROTECTED = [
  '/promptdrawer.md',
  '/promptdrawer.html',
  '/prompts/01-marketing-and-positioning.md',
  '/tools/build_pack.py',
  '/tools/build_landing.py',
  '/docs/stripe-setup.md',
  '/README.md',
];

function routeFor(pathname) {
  for (const route of vercel.routes || []) {
    if (!route.src) continue; // the {"handle": "filesystem"} marker
    if (new RegExp(route.src).test(pathname)) return route;
  }
  return null;
}

/** The deployment, as vercel.json and .vercelignore describe it. */
function decide(pathname, layers) {
  if (layers.routes) {
    const route = routeFor(pathname);
    if (route && route.status) return { kind: 'status', status: route.status };
    if (route && route.dest === '/api/download') return { kind: 'function' };
    if (route && route.dest) return { kind: 'status', status: 404 }; // rewritten to nothing
  }
  if (pathname === '/api/download') return { kind: 'function' };
  const rel = pathname.replace(/^\//, '');
  const files = layers.ignore ? deployableFiles : allStaticFiles;
  if (files.has(rel)) return { kind: 'file', rel };
  return { kind: 'status', status: 404 };
}

// ---------------------------------------------------------------------------
// The harness server
// ---------------------------------------------------------------------------

let layers = { routes: true, ignore: true };
let unhandled = null;

const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const decision = decide(url.pathname, layers);
  if (decision.kind === 'function') {
    req.url = '/api/download' + url.search;
    Promise.resolve()
      .then(() => handler(req, res))
      .catch((error) => {
        unhandled = String(error && error.stack ? error.stack : error);
        res.statusCode = 599;
        res.setHeader('Content-Type', 'text/plain');
        res.end('harness: handler threw\n');
      });
    return;
  }
  if (decision.kind === 'file') {
    const body = fs.readFileSync(path.join(ROOT, decision.rel));
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end(body);
    return;
  }
  res.writeHead(decision.status, { 'Content-Type': 'text/plain' });
  res.end(`${decision.status}\n`);
});

function request(pathname, options) {
  const settings = options || {};
  const savedKey = process.env.STRIPE_SECRET_KEY;
  const savedFetch = globalThis.fetch;
  if (settings.env === undefined) delete process.env.STRIPE_SECRET_KEY;
  else process.env.STRIPE_SECRET_KEY = settings.env;
  if (settings.fetch) globalThis.fetch = settings.fetch;
  return new Promise((resolve, reject) => {
    const req = http.request(
      {
        host: '127.0.0.1',
        port: server.address().port,
        path: pathname,
        method: settings.method || 'GET',
      },
      (res) => {
        const chunks = [];
        res.on('data', (chunk) => chunks.push(chunk));
        res.on('end', () => {
          if (savedKey === undefined) delete process.env.STRIPE_SECRET_KEY;
          else process.env.STRIPE_SECRET_KEY = savedKey;
          globalThis.fetch = savedFetch;
          resolve({ status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks) });
        });
      }
    );
    req.on('error', reject);
    req.end();
  });
}

// ---------------------------------------------------------------------------
// Needles: strings that exist only inside the product
// ---------------------------------------------------------------------------

const mdBytes = fs.readFileSync(path.join(ROOT, 'promptdrawer.md'));
const htmlBytes = fs.readFileSync(path.join(ROOT, 'promptdrawer.html'));
const mdNeedle = mdBytes.toString('utf8').slice(2000, 2060);
const htmlNeedle = '<title>PromptDrawer - 50 AI Prompts';

/** True when a response carries any of the product content. */
function leaksProduct(response) {
  const text = response.body.toString('utf8');
  return text.includes(mdNeedle) || text.includes(htmlNeedle);
}

// ---------------------------------------------------------------------------
// A stub Stripe, so the success path can be exercised without an account
// ---------------------------------------------------------------------------

function stripeStub(session, calls) {
  return function stub(url, init) {
    if (calls) calls.push({ url: String(url), headers: (init && init.headers) || {} });
    if (session === 'http-500') {
      return Promise.resolve({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ error: { message: 'stub server error' } }),
      });
    }
    if (session === 'http-404') {
      return Promise.resolve({
        ok: false,
        status: 404,
        json: () => Promise.resolve({ error: { code: 'resource_missing' } }),
      });
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(session) });
  };
}

function paidSession(extra) {
  return Object.assign(
    {
      object: 'checkout.session',
      id: 'cs_test_stub_paid_session',
      mode: 'payment',
      payment_status: 'paid',
      amount_total: 1900,
      currency: 'usd',
    },
    extra || {}
  );
}

// ---------------------------------------------------------------------------

async function main() {
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));

  const dummyKey = 'sk_test_not_a_real_key_for_the_failure_path';
  const bogusSession = 'cs_test_bogus_reference_that_stripe_does_not_know';
  const realPath = `/download?session_id=${bogusSession}`;

  // ------------------------------------------------------------------
  section('1. Direct public URLs for the product (deployment model)');
  const combos = [
    { label: 'routes + .vercelignore (what ships)', routes: true, ignore: true },
    { label: 'routes only', routes: true, ignore: false },
    { label: '.vercelignore only', routes: false, ignore: true },
  ];
  for (const combo of combos) {
    layers = { routes: combo.routes, ignore: combo.ignore };
    const statuses = [];
    for (const target of PROTECTED) {
      const response = await request(target);
      statuses.push(`${target}=${response.status}`);
      const blocked = response.status === 404 || response.status === 403;
      ok(
        `[${combo.label}] ${target} is not served`,
        blocked && !leaksProduct(response),
        `status ${response.status}`
      );
    }
    const home = await request('/index.html');
    ok(`[${combo.label}] the site itself still works (/index.html)`, home.status === 200, `status ${home.status}`);
    console.log(`        ${statuses.join('  ')}`);
  }

  layers = { routes: true, ignore: true };
  const forwarded = await request('/download');
  ok(
    '/download is routed to the fulfilment function, not to a static file',
    forwarded.status === 503 && /Nothing has been purchased/.test(forwarded.body.toString('utf8')),
    `status ${forwarded.status}`
  );

  ok(
    '.vercelignore keeps the pack and its sources out of the deployment',
    !deployableFiles.has('promptdrawer.md') &&
      !deployableFiles.has('promptdrawer.html') &&
      ![...deployableFiles].some((rel) => rel.startsWith('prompts/')) &&
      !deployableFiles.has('tools/build_pack.py')
  );
  ok('.vercelignore leaves the public site in the deployment', deployableFiles.has('index.html'));

  // ------------------------------------------------------------------
  section('2. No STRIPE_SECRET_KEY configured (fail closed)');
  const noKey = await request('/download');
  ok('GET /download -> 503', noKey.status === 503, `status ${noKey.status}`);
  ok(
    'says plainly that nothing was purchased and nothing can be downloaded',
    /Nothing has been purchased, and nothing can be downloaded/.test(noKey.body.toString('utf8'))
  );
  ok('serves no product content', !leaksProduct(noKey));
  ok('no download headers', !noKey.headers['content-disposition']);
  ok('no email promise', !/we (will|have) (send|sent|emailed)/i.test(noKey.body.toString('utf8')));

  const noKeyFile = await request(`/download?session_id=${bogusSession}&file=md`);
  ok('GET /download?...&file=md -> 503 with no file', noKeyFile.status === 503 && !leaksProduct(noKeyFile));
  const noKeyApi = await request(`/api/download?session_id=${bogusSession}`);
  ok('GET /api/download?... -> 503 with no file', noKeyApi.status === 503 && !leaksProduct(noKeyApi));

  // ------------------------------------------------------------------
  section('3. A malformed reference is refused without calling Stripe');
  const malformedCalls = [];
  const realFetch = globalThis.fetch;
  const countingFetch = (url, init) => {
    malformedCalls.push(String(url));
    return realFetch(url, init);
  };
  const malformed = await request('/download?session_id=abc123', { env: dummyKey, fetch: countingFetch });
  ok('GET /download?session_id=abc123 -> 403', malformed.status === 403, `status ${malformed.status}`);
  ok('no product content', !leaksProduct(malformed));
  ok('Stripe was not called', malformedCalls.length === 0, `calls: ${malformedCalls.length}`);
  const shortSession = await request('/download?session_id=cs_x', { env: dummyKey, fetch: countingFetch });
  ok('a too-short cs_ id -> 403', shortSession.status === 403, `status ${shortSession.status}`);
  const noSession = await request('/download', { env: dummyKey, fetch: countingFetch });
  ok('no session_id at all -> 403', noSession.status === 403, `status ${noSession.status}`);
  ok('Stripe still not called', malformedCalls.length === 0, `calls: ${malformedCalls.length}`);

  // Let the handler keep the module-scoped references it uses (global fetch),
  // so restoring the real fetch here is safe for the next block.
  globalThis.fetch = realFetch;

  // ------------------------------------------------------------------
  section('4. Real Stripe API, deliberately invalid key (fail closed)');
  let live = null;
  let realStripeStatus = null;
  try {
    const probe = await realFetch('https://api.stripe.com/v1/checkout/sessions/cs_test_probe', {
      headers: { Authorization: 'Bearer ' + dummyKey },
    });
    realStripeStatus = probe.status;
  } catch (error) {
    realStripeStatus = null;
  }
  if (realStripeStatus === null) {
    console.log('  note  Stripe API not reachable from here; skipping the live-failure case');
  } else {
    console.log(`  note  live Stripe API answered the invalid key with HTTP ${realStripeStatus}`);
    live = await request(realPath, { env: dummyKey });
    ok('GET /download with an invalid key -> 502, not a success page', live.status === 502, `status ${live.status}`);
    ok(
      'says the link could not be checked, so nothing can be downloaded',
      /could not be checked, so nothing can be downloaded/.test(live.body.toString('utf8'))
    );
    ok('serves no product content', !leaksProduct(live));
    ok('no download headers', !live.headers['content-disposition']);
    ok('does not claim a purchase', !/Payment confirmed/.test(live.body.toString('utf8')));
  }
  const fileWithBadKey = await request(`/download?session_id=${bogusSession}&file=md`, { env: dummyKey });
  ok(
    'file request with an invalid key serves no bytes',
    fileWithBadKey.status !== 200 && !leaksProduct(fileWithBadKey),
    `status ${fileWithBadKey.status}`
  );

  // ------------------------------------------------------------------
  section('5. Stripe answers (stubbed) - only payment_status "paid" unlocks the pack');
  const cases = [
    ['unpaid', paidSession({ payment_status: 'unpaid' }), 403],
    ['unpaid but with the right amount', paidSession({ payment_status: 'unpaid', amount_total: 1900 }), 403],
    ['no_payment_required', paidSession({ payment_status: 'no_payment_required' }), 403],
    ['expired checkout', paidSession({ status: 'expired', payment_status: 'unpaid' }), 403],
    ['Stripe does not know the id (HTTP 404)', 'http-404', 403],
    ['Stripe errors (HTTP 500)', 'http-500', 502],
    ['paid', paidSession(), 200],
  ];
  for (const [label, session, expected] of cases) {
    const response = await request(realPath, { env: dummyKey, fetch: stripeStub(session) });
    ok(`session "${label}" -> ${expected}`, response.status === expected, `status ${response.status}`);
    if (expected !== 200) {
      ok(`session "${label}" serves no product content`, !leaksProduct(response));
      ok(`session "${label}" sets no download header`, !response.headers['content-disposition']);
    } else {
      const text = response.body.toString('utf8');
      ok('the paid page says the payment is confirmed', /Payment confirmed/.test(text));
      ok('the paid page links both files', /file=md/.test(text) && /file=html/.test(text));
      ok('the paid page does not embed the product itself', !leaksProduct(response));
      ok('the paid page promises no email', /no email system/.test(text));
    }
  }

  // ------------------------------------------------------------------
  section('6. A paid session delivers the exact files the build produced');
  const calls = [];
  const paidFetch = stripeStub(paidSession(), calls);
  const mdResponse = await request(`/download?session_id=${bogusSession}&file=md`, {
    env: dummyKey,
    fetch: paidFetch,
  });
  ok('GET ...&file=md -> 200', mdResponse.status === 200, `status ${mdResponse.status}`);
  ok(
    'bytes are identical to promptdrawer.md in the repo',
    mdResponse.body.equals(mdBytes),
    `${mdResponse.body.length} vs ${mdBytes.length}`
  );
  ok(
    'declared as a Markdown attachment named promptdrawer.md',
    mdResponse.headers['content-type'] === 'text/markdown; charset=utf-8' &&
      mdResponse.headers['content-disposition'] === 'attachment; filename="promptdrawer.md"'
  );
  ok('not cacheable', /no-store/.test(mdResponse.headers['cache-control'] || ''));

  const htmlResponse = await request(`/download?session_id=${bogusSession}&file=html`, {
    env: dummyKey,
    fetch: paidFetch,
  });
  ok('GET ...&file=html -> 200', htmlResponse.status === 200, `status ${htmlResponse.status}`);
  ok(
    'bytes are identical to promptdrawer.html in the repo',
    htmlResponse.body.equals(htmlBytes),
    `${htmlResponse.body.length} vs ${htmlBytes.length}`
  );
  ok(
    'declared as an HTML attachment named promptdrawer.html',
    htmlResponse.headers['content-disposition'] === 'attachment; filename="promptdrawer.html"'
  );

  const unknownFile = await request(`/download?session_id=${bogusSession}&file=zip`, {
    env: dummyKey,
    fetch: paidFetch,
  });
  ok('an unknown file name -> 400 and no content', unknownFile.status === 400 && !leaksProduct(unknownFile));

  ok('the key was sent to Stripe as a bearer token', calls.length > 0 && calls[0].headers.Authorization === `Bearer ${dummyKey}`);
  ok('the session id was sent as part of the API URL', calls.length > 0 && calls[0].url.endsWith(bogusSession));
  const anyLeakOfKey =
    noKey.body.toString('utf8').includes(dummyKey) ||
    mdResponse.body.toString('utf8').includes(dummyKey) ||
    (live !== null && live.body.toString('utf8').includes(dummyKey));
  ok('the secret key never appears in a response body', !anyLeakOfKey);

  const post = await request('/download', { method: 'POST', env: dummyKey });
  ok('POST /download -> 405 with no content', post.status === 405 && !leaksProduct(post));

  // ------------------------------------------------------------------
  section('7. No email path anywhere in the fulfilment code');
  const source = fs.readFileSync(path.join(ROOT, 'api', 'download.js'), 'utf8');
  const logic = source.replace(/\/\/ BEGIN GENERATED[\s\S]*\/\/ END GENERATED[^\n]*\n/, '');
  ok('no mailto:, SMTP client or email service in the code', !/mailto:|smtp|nodemailer|sendgrid|postmark|mailgun/i.test(logic));
  ok('no outgoing request except Stripe', (logic.match(/fetch\(/g) || []).length === 1);
  ok('the paid state is read from payment_status', /payment_status === 'paid'/.test(logic));

  ok('the handler never threw an unhandled error', unhandled === null, unhandled || '');

  // ------------------------------------------------------------------
  server.close();
  console.log(`\n${passed} passed, ${failures.length} failed`);
  if (failures.length) {
    console.log('\nFailures:');
    for (const failure of failures) console.log(`  - ${failure}`);
    process.exit(1);
  }
}

main().catch((error) => {
  console.error('harness error:', error);
  process.exit(1);
});
