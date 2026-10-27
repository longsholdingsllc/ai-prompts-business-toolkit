# Lead Qualifier Client

Reusable client for the **Live Lead Qualification Agent** API.

**Live endpoint:** `https://live-lead-qualifier-agent.vercel.app/api/qualify`

## Quick Install / Usage

### Browser / React / Next.js (ESM)

```js
import { qualifyLead } from './lead-qualifier.js';

const result = await qualifyLead({
  name: 'Alex Rivera',
  email: 'alex@growthco.io',
  company: 'GrowthCo',
  title: 'Head of Revenue Operations',
  message: 'Need AI automation for lead scoring',
  budget: '5k-15k',
  timeline: 'this quarter'
});

console.log(result.recommended_action); // "qualify" | "nurture" | "disqualify"
console.log(result.score);              // 0-100
```

### Node.js / Backend

```js
const { qualifyLead } = require('./lead-qualifier.cjs');

const result = await qualifyLead({ ... });
```

## Files

| File | Purpose |
|------|---------|
| `lead-qualifier.js` | ESM version (React, Next.js, modern browsers) |
| `lead-qualifier.cjs` | CommonJS version (Node / older tooling) |
| `examples/` | Ready-to-copy snippets for your specific apps |

## Integration into Your Existing Apps

1. Copy `lead-qualifier.js` (or `.cjs`) into your project (e.g. `src/lib/` or `utils/`).
2. Import and call `qualifyLead()` wherever you receive a new lead (form submit, webhook, CRM sync, etc.).
3. Use the returned `recommended_action` and `score` to route the lead (sales queue, nurture sequence, or reject).

See the `examples/` folder for concrete patterns matching the structure of Income-, Field-service-AI-, and surplus-funds-recovery-os.

## API Contract

- **Method:** POST
- **Body:** JSON object with any of: `name`, `email`, `company`, `title`, `message`, `budget`, `timeline`
- **Response:** `{ success, score, recommended_action, reason, summary, lead_received, timestamp, agent }`

The client handles CORS, JSON parsing, and basic error handling.
