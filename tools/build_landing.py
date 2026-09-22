#!/usr/bin/env python3
"""Build the PromptDrawer landing page (index.html) from the pack sources.

Single source of truth
----------------------
``prompts/*.md`` hold the 50 prompts. ``tools/build_pack.py`` turns them into the
two files a buyer receives. This script turns the same sources into the public
landing page, so no category name, count or prompt title on the page can drift
from the pack:

    python3 tools/build_landing.py            # rewrite index.html
    python3 tools/build_landing.py --check     # fail if it is stale or dishonest

Everything between a ``<!-- BEGIN GENERATED:name -->`` / ``<!-- END GENERATED:name -->``
pair is generated. Edit the surrounding HTML freely by hand; never hand-edit a
generated block, and never type a category name or count into the page.

The claims guard
----------------
This page shipped once with an expired checkout link, an email delivery promise
and a product description that did not match the pack. ``--check`` therefore also
runs a claims guard over the whole page and refuses copy this business cannot
stand behind: no email address or delivery promise, no payment processor, no
proof we do not have, no manufactured urgency, no scripts or remote fetches. It
also requires the page to state plainly that checkout is not open yet.

Standard library only, like the rest of the tooling.
"""

from __future__ import annotations

import html
import importlib.util
import re
import sys
from pathlib import Path

# Importing build_pack must not leave a __pycache__ directory in the repo.
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
BUILD_PACK = Path(__file__).resolve().parent / "build_pack.py"

# How many lines of a real prompt to show in the hero excerpt.
EXCERPT_LINES = 4


class LandingError(Exception):
    """Raised when index.html cannot be generated or fails the claims guard."""


def load_pack_module():
    """Import tools/build_pack.py so both outputs read the same sources."""
    spec = importlib.util.spec_from_file_location("promptdrawer_build_pack", BUILD_PACK)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise LandingError(f"cannot load {BUILD_PACK}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- #
# Generated regions
# --------------------------------------------------------------------------- #


def first_sentence(text: str) -> str:
    """The first sentence of a category intro, used as the card summary."""
    flat = " ".join(text.split())
    match = re.match(r"(.+?[.!?])(\s|$)", flat)
    return match.group(1) if match else flat


def render_hero_ctas(categories: list) -> str:
    total = sum(len(c["prompts"]) for c in categories)
    return (
        '        <div class="hero-ctas">\n'
        f'          <a href="#contents" class="btn btn-primary">Read all {total} prompts</a>\n'
        '          <a href="#availability" class="btn btn-ghost">Why nothing is for sale yet</a>\n'
        "        </div>"
    )


def render_hero_sample(categories: list) -> str:
    """One real prompt from the pack, labelled as an excerpt of that prompt."""
    prompt = categories[0]["prompts"][0]
    category = categories[0]["category"]
    lines = prompt["prompt"].splitlines()
    shown = lines[:EXCERPT_LINES]
    body = "<br>".join("&gt; " + html.escape(line) for line in shown if line.strip())
    if len(lines) > EXCERPT_LINES:
        body += "<br>&gt; ..."
    tail = "" if len(lines) <= EXCERPT_LINES else (
        f" Prompt {prompt['number']} continues past those lines; the rest of the pack is "
        "listed below."
    )
    return (
        '      <div class="prompt-card">\n'
        '        <div class="dot-row" aria-hidden="true">'
        '<span class="dot"></span><span class="dot"></span><span class="dot"></span></div>\n'
        f'        <span class="tag">{html.escape(category.upper())} &middot; PROMPT '
        f'{prompt["number"]} &middot; EXCERPT</span>\n'
        f'        <p class="prompt-name">{html.escape(prompt["title"])}</p>\n'
        f'        <p class="prompt-text">{body}</p>\n'
        f'        <p class="prompt-note">One prompt out of the pack, copied from its file and '
        f"cut short here.{html.escape(tail)}</p>\n"
        "      </div>"
    )


def render_drawers(categories: list) -> str:
    total = sum(len(c["prompts"]) for c in categories)
    out = [
        '  <section class="drawers-section">',
        f'    <h2 class="section-title">{len(categories)} drawers, {total} prompts</h2>',
        '    <p class="section-sub">Every prompt in the pack, grouped by the job it is for. '
        'The counts below are read from the pack files themselves.</p>',
        '    <div class="drawers">',
    ]
    for category in categories:
        count = len(category["prompts"])
        numbers = [p["number"] for p in category["prompts"]]
        out.append(
            f'      <div class="drawer"><span class="count">{count} PROMPTS'
            f' &middot; {numbers[0]}-{numbers[-1]}</span>'
            f'<h3>{html.escape(category["category"])}</h3>'
            f'<p>{html.escape(first_sentence(category["intro"]))}</p></div>'
        )
    out.append("    </div>")
    out.append("  </section>")
    return "\n".join(out)


def render_contents(categories: list) -> str:
    total = sum(len(c["prompts"]) for c in categories)
    out = [
        '  <section id="contents" class="contents-section">',
        f'    <h2 class="section-title">All {total} prompts, by name</h2>',
        '    <p class="section-sub">This is the full contents list of the pack, generated from the '
        "pack files. Nothing here arrives in a message and there is nothing to sign up for: the "
        "list is the whole preview.</p>",
        '    <div class="contents-grid">',
    ]
    for category in categories:
        count = len(category["prompts"])
        out.append('      <div class="contents-cat">')
        out.append(
            f'        <h3><span class="count">{count} PROMPTS</span>'
            f'{html.escape(category["category"])}</h3>'
        )
        out.append('        <ul class="contents-list">')
        for prompt in category["prompts"]:
            out.append(
                f'          <li><span class="num">{prompt["number"]}</span>'
                f'{html.escape(prompt["title"])}</li>'
            )
        out.append("        </ul>")
        out.append("      </div>")
    out.append("    </div>")
    out.append("  </section>")
    return "\n".join(out)


def render_pack_facts(categories: list) -> str:
    total = sum(len(c["prompts"]) for c in categories)
    return (
        "      <div>\n"
        '        <h3 style="color:var(--paper); font-size:1.2rem;">PromptDrawer - 50 AI prompts '
        "for solo and small-business operators</h3>\n"
        "        <ul>\n"
        f'          <li>All {len(categories)} categories, {total} prompts, numbered 1-{total}</li>\n'
        '          <li>Each prompt carries a when-to-use line, a fill-in note for every placeholder, '
        "and a tip for what to do with the answer</li>\n"
        '          <li>Two files: <code>promptdrawer.md</code> (Markdown) and '
        '<code>promptdrawer.html</code> (print-ready)</li>\n'
        "          <li>Plain text, so it works with ChatGPT, Claude, Gemini, Copilot or any other "
        "assistant</li>\n"
        "        </ul>\n"
        "      </div>"
    )


REGIONS = {
    "hero-ctas": render_hero_ctas,
    "hero-sample": render_hero_sample,
    "drawers": render_drawers,
    "contents": render_contents,
    "pack-facts": render_pack_facts,
}


# --------------------------------------------------------------------------- #
# Injection
# --------------------------------------------------------------------------- #


def region_pattern(name: str) -> re.Pattern:
    return re.compile(
        r"(?P<indent>[ \t]*)<!-- BEGIN GENERATED:" + re.escape(name) + r" -->"
        r"(?P<body>.*?)"
        r"<!-- END GENERATED:" + re.escape(name) + r" -->",
        re.S,
    )


def inject(document: str, name: str, body: str) -> str:
    pattern = region_pattern(name)
    if not pattern.search(document):
        raise LandingError(f"index.html has no 'BEGIN GENERATED:{name}' region")
    replacement = (
        f"{pattern.search(document).group('indent')}<!-- BEGIN GENERATED:{name} -->\n"
        f"{body.rstrip(chr(10))}\n"
        f"{pattern.search(document).group('indent')}<!-- END GENERATED:{name} -->"
    )
    return pattern.sub(lambda _match: replacement, document, count=1)


def build_document(template: str, categories: list) -> str:
    found = set(re.findall(r"<!-- BEGIN GENERATED:([a-z-]+) -->", template))
    unknown = sorted(found - set(REGIONS))
    if unknown:
        raise LandingError(f"index.html declares regions this tool does not know: {unknown}")
    document = template
    for name, render in REGIONS.items():
        document = inject(document, name, render(categories))
    return document


# --------------------------------------------------------------------------- #
# Claims guard
# --------------------------------------------------------------------------- #

# (pattern, why it is refused). Case-insensitive.
FORBIDDEN = [
    (r"mailto:", "a mailto: link"),
    (r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}", "an email address"),
    (r"stripe", "a payment processor - this business cannot take a payment"),
    (r"supabase|posthog|google-analytics|gtag\(|plausible", "a tracking or backend service"),
    (r"<script", "a script tag - the page needs no JavaScript"),
    (r"fetch\(", "a network call"),
    (r"sent to your inbox|to your inbox|check your inbox", "delivery to an inbox we cannot reach"),
    (r"right after payment|after payment", "a delivery promise tied to a payment"),
    (r"by email|emailed|e-mail", "an email delivery promise"),
    (r"we will send|we'll send|send them to me", "a promise to send something"),
    (r"lifetime access|lifetime updates|free updates|future updates", "an updates promise we cannot deliver"),
    (r"guarantee|money-back|refund", "a guarantee we have no mechanism to honour"),
    (r"testimonial|customer review|trusted by|\b5-star\b|five-star", "proof we do not have"),
    (r"\b\d[\d,]*\+?\s*(customers|buyers|users|subscribers|downloads|sales)\b", "a customer count we do not have"),
    (r"limited time|act now|only \d+ (spots|left)|final notice|\burgent\b", "manufactured urgency"),
    (r"best-?sell(er|ing)", "a sales claim we cannot ground"),
    (r"lorem ipsum|\btodo\b|\btbd\b|\bxxxx+\b", "a leftover template value"),
    (r"buy the pack|add to cart|buy now", "an invitation to buy a checkout that does not exist"),
]

MUST_HAVE = [
    ("Checkout is not open yet", "the page must say plainly that checkout is not open"),
    ("intended launch price", "any price shown must be labelled as an intended launch price"),
]


def claims_guard(document: str) -> list:
    problems = []
    lowered = document.lower()
    for pattern, why in FORBIDDEN:
        match = re.search(pattern, lowered)
        if match:
            line = lowered[: match.start()].count("\n") + 1
            problems.append(f"line {line}: found {why} -> {match.group(0)!r}")
    for needle, why in MUST_HAVE:
        if needle.lower() not in lowered:
            problems.append(f"missing: {why} (expected {needle!r})")
    if re.search(r"\$\s*\d", document) and "not yet on sale" not in lowered:
        problems.append("a price is shown without saying it is not yet on sale")
    return problems


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def main() -> int:
    check_only = "--check" in sys.argv[1:]
    try:
        categories = load_pack_module().load_pack()
        template = INDEX.read_text(encoding="utf-8")
        fresh = build_document(template, categories)
    except LandingError as error:
        print(f"LANDING FAILED: {error}", file=sys.stderr)
        return 1
    except Exception as error:  # source errors from build_pack land here
        print(f"LANDING FAILED: {error}", file=sys.stderr)
        return 1

    total = sum(len(c["prompts"]) for c in categories)
    problems = claims_guard(fresh)

    if check_only:
        failed = False
        if fresh != template:
            print("OUT OF DATE: index.html - re-run python3 tools/build_landing.py", file=sys.stderr)
            failed = True
        if problems:
            for problem in problems:
                print(f"CLAIMS GUARD: {problem}", file=sys.stderr)
            failed = True
        if failed:
            return 1
        print(
            f"Up to date: index.html matches {total} prompts in {len(categories)} categories; "
            f"claims guard clean ({len(FORBIDDEN)} patterns)"
        )
        return 0

    INDEX.write_text(fresh, encoding="utf-8")
    print(f"Built index.html from the pack: {total} prompts, {len(categories)} categories")
    for category in categories:
        print(f"  {len(category['prompts']):>2}  {category['category']}")
    for problem in problems:
        print(f"CLAIMS GUARD: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
