# Injected: lead-qualifier-client

This folder is a verbatim copy of the `lead-qualifier-client` library,
injected into this repository under `shared/lead-qualifier-client/` on
2026-10-27 from the source repository
`longsholdingsllc/lead-qualifier-client`.

It was placed at this top-level `shared/` location, outside every build
path, so adding it cannot break this host app's build. No existing files
in this host were modified.

## What this library is

A reusable, dependency-free client for the **Live Lead Qualification
Agent** API. It exposes a single async function, `qualifyLead(lead)`,
that sends a lead to the live agent and returns its score and routing
recommendation.

- `lead-qualifier.js` — ESM version (React, Next.js, modern browsers)
- `lead-qualifier.cjs` — CommonJS version (Node / older tooling)
- `examples/` — ready-to-copy integration snippets:
  - `examples/react-form-integration.js` — React form submit handler
  - `examples/nextjs-api-route.ts` — Next.js API route wrapper
  - `examples/python-backend.py` — FastAPI / Python backend route

## API it talks to

- **Backend:** Live Lead Qualification Agent — source repository
  `longsholdingsllc/live-lead-qualifier-agent`, deployed on Vercel.
- **Endpoint:** `POST https://live-lead-qualifier-agent.vercel.app/api/qualify`
- **Request body (JSON, all fields optional):** `name`, `email`,
  `company`, `title`, `message`, `budget`, `timeline`
- **Response:** `{ success, score, recommended_action, reason, summary,
  lead_received, timestamp, agent }`, where `score` is 0–100 and
  `recommended_action` is `"qualify"`, `"nurture"`, or `"disqualify"`.
  Per the backend README, it is a public production endpoint that scores
  inbound leads in real time — e.g. a strong lead returns `score: 100`,
  `recommended_action: "qualify"`, `summary: "Lead scored 100/100 → QUALIFY"`.
- On network/API failure the client does not throw: it logs the error and
  returns a safe fallback `{ success: false, score: 0,
  recommended_action: "nurture", reason: "API unavailable – defaulting
  to nurture", ... }` so calling form code does not crash.

## Minimal usage in this host

ESM (browser / React / Next.js) — adjust the relative import path to
where your page/form file lives:

```js
import { qualifyLead } from './shared/lead-qualifier-client/lead-qualifier.js';
// also available as the default export: import qualifyLead from '...'

const result = await qualifyLead({
  name: 'Alex Rivera',
  email: 'alex@growthco.io',
  company: 'GrowthCo',
  title: 'Head of Revenue Operations',
  message: 'Need AI automation for lead scoring',
  budget: '5k-15k',
  timeline: 'this quarter'
});

console.log(result.score);              // 0-100
console.log(result.recommended_action); // "qualify" | "nurture" | "disqualify"

if (result.recommended_action === 'qualify') {
  // route to sales / CRM immediately
} else if (result.recommended_action === 'nurture') {
  // add to a nurture sequence
} else {
  // low priority / disqualify
}
```

CommonJS (Node backend):

```js
const { qualifyLead } = require('./shared/lead-qualifier-client/lead-qualifier.cjs');

const result = await qualifyLead({ name, email, company, title, message, budget, timeline });
```

Call `qualifyLead()` wherever this host receives a new lead (form submit,
webhook, or CRM sync) and route the lead using the returned `score` and
`recommended_action`. See `README.md` and `examples/` in this folder for
the full contract and framework-specific patterns.
