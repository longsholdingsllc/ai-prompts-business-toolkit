# Stripe setup for PromptDrawer fulfilment

**Status: not done. No Stripe account is connected to this project, and nothing in
this document has been run against a real Stripe account.** Every step below is a
description of documented Stripe and Vercel behaviour plus the checks that must be
run once an account exists. Nothing here is a test result. Read the last section
before treating any of it as working.

The point of the work this document supports: the product is finished and the
delivery mechanism is built and tested, so completing these steps should be the
only thing standing between the business and a first sale. Nothing in the flow
uses email, because this business has no email system.

---

## How delivery works (already built)

| Piece | What it does |
| --- | --- |
| `/download?session_id=...` | A page served by `api/download.js`. `vercel.json` rewrites `/download` to that function. |
| `/api/download?session_id=...` | The same function directly. Both URLs are identical in behaviour. |
| `?file=md` / `?file=html` | Serves `promptdrawer.md` or `promptdrawer.html` as a download, but only after the same paid check. |
| `STRIPE_SECRET_KEY` | Server-side only. The function reads this one environment variable and calls Stripe's API over HTTPS. No SDK, no dependency, no database. |

The function asks Stripe one question - *is this checkout session's
`payment_status` `paid`?* - and serves the pack only when the answer is yes. It
deliberately does not check the amount, the currency or the product. Anything
else - no key, no session id, a malformed or unknown reference, an unpaid or
expired checkout, Stripe being unreachable or refusing the key - gets an honest
page saying that nothing was purchased and nothing can be downloaded, with no
file bytes and no receipt.

The two buyer files are **not** public files. They are compiled into the function
by `tools/build_pack.py` between the `GENERATED: pack-files` markers, and they are
kept out of the static deployment twice over: `.vercelignore` removes them (and
the prompt sources in `prompts/`) from the deployment, and `vercel.json` returns
404 for their URLs. A direct request for either file must never return the pack.

---

## Step 1 - Create the product and its price

In the Stripe Dashboard, with test mode on first:

1. **Products → Add product.**
2. Name: `PromptDrawer - 50 AI prompts for solo and small-business operators`.
   Description: keep it to what is true - 50 paste-ready prompts in 8 categories,
   delivered as a Markdown file and a print-ready HTML file.
3. Pricing: **One-time**, **$19 USD**.
   **$19 is the intended launch price.** No price is stated anywhere in the
   product files, and nothing has been charged to anyone.
4. No shipping, no tax configuration beyond whatever the account requires.

## Step 2 - Create the Payment Link

1. From the price, **Create payment link**.
2. After payment: choose **Redirect to your website** (not the confirmation page).
3. Paste exactly this as the redirect URL, including the braces:

   ```
   https://ai-prompts-business-toolkit.vercel.app/download?session_id={CHECKOUT_SESSION_ID}
   ```

   Stripe substitutes the real Checkout Session id for `{CHECKOUT_SESSION_ID}`.
   That placeholder in a Payment Link's redirect URL is documented by Stripe at
   <https://docs.stripe.com/payment-links/post-payment>. **This has not been
   tested by us against an account.**
4. Do not publish the link yet. Run Step 4 first, in test mode.

Note on the URL shape: if `/download` ever misbehaves after a deploy,
`https://ai-prompts-business-toolkit.vercel.app/api/download?session_id={CHECKOUT_SESSION_ID}`
is the same page with no rewrite involved, and the redirect URL can be changed to
it in one edit. The check list in Step 4 covers both.

## Step 3 - Set the environment variable in Vercel

In the Vercel project → **Settings → Environment Variables**, add:

| Name | Value | Environments |
| --- | --- | --- |
| `STRIPE_SECRET_KEY` | the secret key (`sk_test_...` while testing, `sk_live_...` when live) | Production (add Preview as well if preview deploys should serve downloads) |

Rules that matter:

- Server-side only. Never put it in client code, never prefix it with `VITE_` or
  `NEXT_PUBLIC_`, never commit it. The function reads `process.env.STRIPE_SECRET_KEY`
  at request time.
- The **publishable** key and the Payment Link URL are not needed by this code at
  all.
- A new environment variable only reaches the running function after a new
  deployment, so redeploy after adding it.
- Nothing is written to a `.env` file anywhere.

## Step 4 - Verify before publishing the payment link

Run these against the live site **after the deploy that adds Step 3**, in test
mode, before telling anyone the product is buyable.

```bash
BASE=https://ai-prompts-business-toolkit.vercel.app

# The product must not be a public file. Expect 404 for every one of these.
for p in promptdrawer.md promptdrawer.html \
         prompts/01-marketing-and-positioning.md tools/build_pack.py README.md; do
  printf '%s -> %s\n' "$p" "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/$p")"
done

# The site itself must still work. Expect 200.
curl -s -o /dev/null -w 'index.html -> %{http_code}\n' "$BASE/index.html"

# The download page with no usable reference.
#   no STRIPE_SECRET_KEY set  -> 503, "Nothing has been purchased..."
#   key set, no session id    -> 403, same plain statement
curl -s -w '\nSTATUS %{http_code}\n' "$BASE/download" | tail -20

# A reference Stripe does not know. Expect 403 and no files.
curl -s -w '\nSTATUS %{http_code}\n' \
  "$BASE/download?session_id=cs_test_does_not_exist_for_real" | tail -20

# Ask for a file without a paid session. Expect no 200 and no pack bytes.
curl -s -o /dev/null -w 'file without payment -> %{http_code}\n' \
  "$BASE/download?session_id=cs_test_does_not_exist_for_real&file=md"
```

Then make a real test-mode purchase with a Stripe test card, let the redirect land
on `/download?session_id=cs_test_...`, and confirm the page says **"Payment
confirmed"** and offers two download links. Download both and check they open.
While Stripe is in test mode nothing is charged.

If that page 404s, the rewrite in `vercel.json` is the first thing to look at;
point the Payment Link's redirect at `/api/download?...` as the immediate fix.

## What has been verified, and what has not

**Verified here, without a Stripe account** - `node tests/verify_fulfilment.js`
(85 checks, all passing, exit 0):

- With no `STRIPE_SECRET_KEY`: `/download` and `/api/download` answer `503` with
  the plain statement that nothing has been purchased and nothing can be
  downloaded, serve no product bytes and set no download headers.
- A malformed reference (`abc123`, a too-short `cs_` id, or none at all) is
  refused with `403` **without any call to Stripe**.
- Against the **real Stripe API** with a deliberately invalid key (Stripe answered
  `401`, logged by the run): the page returns `502` and says the link could not be
  checked, so nothing can be downloaded. No product bytes, no receipt, no claim
  that a purchase happened.
- With Stripe's answers stubbed: `payment_status` of `unpaid`, `no_payment_required`
  and an expired checkout all return `403`; an `unpaid` session whose
  `amount_total` is nonetheless 1900 (the intended price) is **still** `403` -
  the amount is not what unlocks the pack; an unknown id (`404`) returns `403`; a
  Stripe error (`500`) returns `502`.
- A session with `payment_status: "paid"` returns the confirmation page, and the
  bytes served for each file are **byte-for-byte identical** to `promptdrawer.md`
  and `promptdrawer.html` as built in this repository.
- The secret key never appears in any response body, and the fulfilment code
  contains no mail client, no `mailto:` and no outbound request other than the one
  to Stripe.
- The deployment model in `vercel.json` + `.vercelignore` blocks every product and
  source URL with `404` under two independent layers (routes alone, and
  `.vercelignore` alone), while `/index.html` keeps returning `200`.

**Not verified - nobody has done any of this:**

- Everything in Steps 1, 2 and 3 above. There is no Stripe account connected, so
  no product, price, Payment Link or key exists.
- That Stripe substitutes `{CHECKOUT_SESSION_ID}` in a Payment Link redirect for
  this account (documented by Stripe, untested here).
- That the deployed Vercel project behaves exactly as the local model above
  predicts. `vercel.json` and `.vercelignore` were written to documented
  behaviour and modelled locally; they have not been run on Vercel from here.
  Step 4 is the check for that, and it needs to pass before any real buyer sees
  the page.
- Any payment, refund, tax, receipt or email behaviour whatsoever. No money has
  ever moved through this business.

## Honest limitations of this design

- **Possession of the link is access.** Anyone holding a paid
  `/download?session_id=...` URL can download the pack, and can do so again later.
  There is no login, no expiry and no per-buyer binding. For a $19 pack that is an
  acceptable trade for having no accounts and no database; if it ever needs to be
  tighter, the fix is a signed, expiring link, not something this design already
  does.
- **The pack is also in a public Git repository.** `prompts/*.md`, and until this
  change `promptdrawer.md` and `promptdrawer.html` at the site root, exist in
  `longsholdingsllc/ai-prompts-business-toolkit` on GitHub. Whatever the site
  does, someone determined can read the prompts from the repository history. If
  the pack must genuinely be paid-only, the repository has to be made private or
  the prompt sources moved out of it. **That is an owner/lead decision, and site
  configuration cannot fix it.**
- **The landing page is still in its honest "checkout is not open yet" state.**
  `index.html` is generated by `tools/build_landing.py`, whose claims guard refuses
  any buy call to action, the word "stripe", and any email promise, and requires
  the page to say checkout is not open. Turning checkout on means changing the
  landing page and its guard together - a follow-up change, deliberately not made
  here.
- **No email, at any point, by design.** Nothing is sent to a buyer, and no copy
  anywhere promises that anything will be.

## Cost

One serverless function with zero dependencies, no database, no storage and no
background jobs. The function carries its own copy of the pack, so there is
nothing else to pay for beyond the static site that already exists.
