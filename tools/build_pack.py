#!/usr/bin/env python3
"""Build the distributable PromptDrawer pack from the prompt sources.

Single source of truth
----------------------
``prompts/*.md`` hold the 50 prompts, one file per category. This script reads
them, validates them, and writes the two files a buyer receives:

    promptdrawer.md     - the whole pack as one Markdown file
    promptdrawer.html   - a self-contained, print-ready HTML file

Both outputs are generated. Never edit ``promptdrawer.md`` or
``promptdrawer.html`` by hand: edit ``prompts/*.md`` and re-run

    python3 tools/build_pack.py

The script uses only the Python standard library, so it runs anywhere with
Python 3.8+ and no install step.

Source format (one file per category, files sorted by name)
----------------------------------------------------------
    # Category Name

    Optional one-paragraph category intro.

    ## 1. Prompt Title

    **When to use:** one or two sentences.

    **Prompt:**

    ```text
    The full prompt text, with [SQUARE BRACKET] placeholders.
    ```

    **Fill in:**

    - `[PLACEHOLDER]` - what belongs there.

    **Tip:** what to do with the output.

Validation is strict on purpose: numbering must run 1..N with no gaps or
repeats, titles must be unique, and every prompt must carry all four parts.
A broken source file fails the build rather than shipping a half-full pack.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "prompts"
OUT_MD = ROOT / "promptdrawer.md"
OUT_HTML = ROOT / "promptdrawer.html"

PACK_TITLE = "PromptDrawer"
PACK_SUBTITLE = "50 AI prompts for solo and small-business operators"
PACK_VERSION = "1.0"
PACK_DATE = "2026-09-22"

INTRO_MD = """\
## What this is

Fifty prompts you can paste into an AI assistant (ChatGPT, Claude, Gemini, Copilot,
or anything similar) to get real work done in a business you run mostly or entirely
by yourself.

Every prompt is built the same way:

- **When to use** tells you the situation it fits, so you can find the right one in
  seconds instead of reading all fifty.
- **The prompt** is the full text to copy. Anything in `[SQUARE BRACKETS]` is a
  detail only you know.
- **Fill in** lists each placeholder and says exactly what belongs there.
- **Tip** tells you what to do with the output, or how to push it further.

## How to use it

1. Find the prompt that matches the job in front of you, using the contents list.
2. Replace every `[SQUARE BRACKET]` with your own details. Delete the ones that do
   not apply rather than leaving them in.
3. Paste the whole thing into your AI assistant and send it.
4. Read the answer critically. The prompt asks the assistant to work from what you
   gave it and to ask you questions instead of inventing facts, but you are still
   the one who knows your business.
5. If the first answer is close but not right, use the follow-up line in the Tip
   rather than starting over.

Two things worth knowing:

- **Long prompts work better than short ones.** The bracketed details are what make
  the output specific to you. A prompt with the placeholders left blank gives you
  generic advice, which you did not need a file for.
- **Treat the output as a draft.** The prompts are written to keep an AI assistant
  from making up numbers about your business, but anything it states as a fact
  about your market should still be checked before you rely on it.

## What is not claimed here

This is a set of written prompts. It is not a course, not a subscription, not
software, and it does not connect to any of your accounts.

It makes no promise about results, savings, revenue or time. Nobody has measured
those for this pack, and it would be dishonest to state them. What is true is
narrow and checkable: there are 50 prompts, each one is paste-ready, every
placeholder is marked and explained, and each one comes with a tip.

"""


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #

PROMPT_START = re.compile(r"^##\s+(\d+)\.\s+(.+?)\s*$", re.M)


class SourceError(Exception):
    """Raised when a prompt source file does not match the expected format."""


def _one(pattern: str, chunk: str, label: str, path: Path) -> str:
    match = re.search(pattern, chunk, re.S)
    if not match:
        raise SourceError(f"{path.name}: a prompt is missing its {label} part")
    return match.group(1).strip()


def parse_category(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")

    title_match = re.match(r"^#\s+(.+?)\s*$", raw, re.M)
    if not title_match:
        raise SourceError(f"{path.name}: no '# Category Name' heading")
    category = title_match.group(1).strip()

    heads = list(PROMPT_START.finditer(raw))
    if not heads:
        raise SourceError(f"{path.name}: no prompts found")

    first_head = heads[0].start()
    intro = raw[title_match.end():first_head].strip()
    intro = "\n".join(line for line in intro.splitlines() if not line.startswith("#"))

    prompts = []
    for index, head in enumerate(heads):
        end = heads[index + 1].start() if index + 1 < len(heads) else len(raw)
        chunk = raw[head.end():end]
        number = int(head.group(1))

        body = _one(r"\*\*Prompt:\*\*\s*```[a-zA-Z]*\n(.*?)\n```", chunk, "prompt text", path)
        when = _one(r"\*\*When to use:\*\*\s*(.+?)(?=\n\*\*|\Z)", chunk, "when-to-use", path)
        tip = _one(r"\*\*Tip:\*\*\s*(.+?)(?=\n\*\*|\Z)", chunk, "tip", path)
        note_match = re.search(r"\*\*Note:\*\*\s*(.+?)(?=\n\*\*|\Z)", chunk, re.S)
        note = " ".join(note_match.group(1).split()) if note_match else ""
        fill_raw = _one(r"\*\*Fill in:\*\*\s*(.*?)(?=\n\*\*|\Z)", chunk, "fill-in list", path)

        fills = []
        for line in fill_raw.splitlines():
            line = line.strip()
            if not line:
                continue
            item = re.match(r"^[-*]\s+(.+?)\s+-\s+(.+)$", line)
            if not item or "[" not in item.group(1):
                raise SourceError(f"{path.name}: unreadable 'Fill in' line: {line!r}")
            fills.append((item.group(1).strip(), item.group(2).strip()))
        if not fills:
            raise SourceError(f"{path.name}: prompt {number} has no 'Fill in' entries")

        prompts.append(
            {
                "number": number,
                "title": head.group(2).strip(),
                "when": " ".join(when.split()),
                "prompt": body.strip("\n").rstrip(),
                "fills": fills,
                "tip": " ".join(tip.split()),
                "note": note,
            }
        )

    return {"slug": path.stem, "category": category, "intro": intro, "prompts": prompts}


def load_pack() -> list:
    files = sorted(SRC_DIR.glob("*.md"))
    if not files:
        raise SourceError(f"no source files in {SRC_DIR}")
    categories = [parse_category(path) for path in files]

    seen_numbers, seen_titles = [], []
    for category in categories:
        for prompt in category["prompts"]:
            seen_numbers.append(prompt["number"])
            seen_titles.append(prompt["title"].lower())
    expected = list(range(1, len(seen_numbers) + 1))
    if sorted(seen_numbers) != expected:
        missing = sorted(set(expected) - set(seen_numbers))
        extra = sorted(n for n in seen_numbers if n not in expected)
        raise SourceError(f"numbering is not 1..{len(expected)}; missing={missing} duplicated/extra={extra}")
    if len(set(seen_titles)) != len(seen_titles):
        dupes = sorted({t for t in seen_titles if seen_titles.count(t) > 1})
        raise SourceError(f"duplicate prompt titles: {dupes}")
    for category in categories:
        for prompt in category["prompts"]:
            if "[" not in prompt["prompt"]:
                raise SourceError(f"prompt {prompt['number']} ({prompt['title']}) has no placeholders")
    return categories


# --------------------------------------------------------------------------- #
# Markdown output
# --------------------------------------------------------------------------- #


def anchor(category_index: int) -> str:
    return f"category-{category_index + 1}"


def build_markdown(categories: list) -> str:
    total = sum(len(c["prompts"]) for c in categories)
    out = []
    out.append("---")
    out.append(f"title: {PACK_TITLE} - {PACK_SUBTITLE}")
    out.append(f"version: {PACK_VERSION}")
    out.append(f"date: {PACK_DATE}")
    out.append(f"prompts: {total}")
    out.append(f"categories: {len(categories)}")
    out.append("format: Markdown")
    out.append("---")
    out.append("")
    out.append(f"# {PACK_TITLE}")
    out.append("")
    out.append(f"### {PACK_SUBTITLE}")
    out.append("")
    out.append(f"Version {PACK_VERSION} - {PACK_DATE} - {total} prompts in {len(categories)} categories")
    out.append("")
    out.append(INTRO_MD.rstrip())
    out.append("")

    out.append("## Contents")
    out.append("")
    for index, category in enumerate(categories):
        count = len(category["prompts"])
        first = category["prompts"][0]["number"]
        last = category["prompts"][-1]["number"]
        out.append(f"- **{category['category']}** - {count} prompts ({first}-{last})")
        for prompt in category["prompts"]:
            out.append(f"  - {prompt['number']}. {prompt['title']}")
    out.append("")

    for category in categories:
        count = len(category["prompts"])
        out.append("---")
        out.append("")
        out.append(f"## {category['category']}")
        out.append("")
        out.append(f"*{count} prompt{'s' if count != 1 else ''}*")
        out.append("")
        if category["intro"]:
            out.append(category["intro"])
            out.append("")
        for prompt in category["prompts"]:
            out.append(f"### {prompt['number']}. {prompt['title']}")
            out.append("")
            out.append(f"**When to use:** {prompt['when']}")
            out.append("")
            out.append("**Prompt**")
            out.append("")
            out.append("```text")
            out.append(prompt["prompt"])
            out.append("```")
            out.append("")
            out.append("**Fill in**")
            out.append("")
            for label, meaning in prompt["fills"]:
                out.append(f"- {label} - {meaning}")
            out.append("")
            if prompt["note"]:
                out.append(f"**Note:** {prompt['note']}")
                out.append("")
            out.append(f"**Tip:** {prompt['tip']}")
            out.append("")

    out.append("---")
    out.append("")
    out.append(f"*{PACK_TITLE} - {PACK_SUBTITLE}. Version {PACK_VERSION}, {PACK_DATE}.*")
    out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# HTML output
# --------------------------------------------------------------------------- #

PLACEHOLDER = re.compile(r"\[[^\[\]\n]{2,60}\]")


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def mark_placeholders(escaped_text: str) -> str:
    return PLACEHOLDER.sub(lambda m: f'<span class="ph">{m.group(0)}</span>', escaped_text)


def inline_code(text: str) -> str:
    """Escape text, then turn `backticked` runs into inline code."""
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", esc(text))


CSS = """
:root{--ink:#151A20;--muted:#5A6470;--rule:#D9DEE4;--accent:#1F5C4A;--wash:#F4F6F5;--ph:#8A4B12}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:#fff;color:var(--ink);
 font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
 font-size:17px;line-height:1.6;}
.wrap{max-width:820px;margin:0 auto;padding:0 22px 72px}
h1,h2,h3,h4{line-height:1.2;margin:0 0 .4em;letter-spacing:-.01em}
h1{font-size:2.1rem}
h2{font-size:1.5rem;padding-top:.2em}
h3{font-size:1.16rem}
p{margin:0 0 1em}
a{color:var(--accent)}
code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.92em}
.masthead{border-bottom:3px solid var(--ink);padding:40px 0 26px;margin-bottom:32px}
.masthead .kicker{font-size:.75rem;letter-spacing:.16em;text-transform:uppercase;color:var(--accent);font-weight:600;margin:0 0 10px}
.masthead h1{margin-bottom:.25em}
.masthead .sub{font-size:1.08rem;color:var(--muted);margin:0}
.meta{margin:16px 0 0;font-size:.86rem;color:var(--muted)}
.intro{background:var(--wash);border:1px solid var(--rule);border-radius:4px;padding:26px 26px 10px;margin:0 0 40px}
.intro h2{font-size:1.05rem;letter-spacing:.02em;text-transform:uppercase;color:var(--accent)}
.intro h3{font-size:1.05rem;margin-top:1.6em}
.intro ol,.intro ul{margin:0 0 1.2em;padding-left:1.25em}
.intro li{margin-bottom:.45em}
.toc{border:1px solid var(--rule);border-radius:4px;padding:24px 26px;margin:0 0 44px}
.toc h2{font-size:1.05rem;letter-spacing:.02em;text-transform:uppercase;color:var(--accent)}
.toc ol{list-style:none;margin:0;padding:0;columns:2;column-gap:34px}
.toc>ol>li{break-inside:avoid;margin-bottom:.9em;font-weight:600}
.toc ol ol{margin:.35em 0 0;padding-left:14px;font-weight:400}
.toc ol ol li{font-size:.92rem;color:var(--muted);margin-bottom:.15em}
.toc a{text-decoration:none}
.toc a:hover{text-decoration:underline}
.cat{margin:0 0 52px;padding-top:6px;border-top:2px solid var(--ink)}
.cat .count{display:block;font-size:.8rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);font-weight:600;margin:0 0 14px}
.cat .catintro{color:var(--muted);margin-bottom:28px}
article.prompt{border:1px solid var(--rule);border-radius:4px;padding:22px 24px;margin:0 0 26px;break-inside:avoid;page-break-inside:avoid}
article.prompt h3{margin-bottom:.5em}
article.prompt h3 .num{color:var(--accent);font-variant-numeric:tabular-nums}
.when{margin-bottom:1.1em}
.prompttext{white-space:pre-wrap;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
 font-size:14.5px;line-height:1.62;background:var(--wash);border:1px solid var(--rule);
 border-left:4px solid var(--accent);border-radius:3px;padding:16px 18px;margin:0 0 1.1em;overflow-wrap:break-word}
.ph{color:var(--ph);font-weight:600}
.fill{margin-bottom:1em}
.note{background:var(--wash);border-left:3px solid var(--muted);padding:.7em .9em;margin:0 0 1em;font-size:.95em}
.note strong{color:var(--muted)}
.fill ul{margin:.4em 0 0;padding-left:1.15em}
.fill li{margin-bottom:.4em}
.tip{border-top:1px dashed var(--rule);padding-top:.9em;margin:0}
.tip strong{color:var(--accent)}
footer{border-top:3px solid var(--ink);margin-top:20px;padding-top:18px;color:var(--muted);font-size:.88rem}
@media (max-width:640px){
 body{font-size:16px}
 .wrap{padding:0 16px 56px}
 h1{font-size:1.65rem}
 .toc ol{columns:1}
 .toc,.intro{padding:20px 18px 2px}
 article.prompt{padding:18px 16px}
 .prompttext{font-size:13.5px;padding:13px 13px}
}
@media print{
 @page{size:A4;margin:16mm 15mm}
 body{font-size:10.6pt;line-height:1.45;color:#000}
 .wrap{max-width:none;padding:0}
 h1{font-size:19pt}
 h2{font-size:14pt}
 h3{font-size:11.6pt}
 a{color:#000;text-decoration:none}
 .intro,.toc{border:0;background:none;padding:0}
 .toc ol{columns:2}
 .masthead{padding-top:0}
 .cat{border-top:1px solid #000;break-before:page;page-break-before:always}
 .cat:first-of-type{break-before:auto;page-break-before:auto}
 article.prompt{border:0;padding:0;margin:0 0 15px;break-inside:avoid;page-break-inside:avoid}
 .prompttext{background:none;border:0;border-left:2px solid #000;padding:0 0 0 10px;font-size:9.3pt;line-height:1.4}
 .ph{color:#000}
 .tip{border-top:1px solid #999}
 footer{break-before:avoid}
}
"""


def build_html_body(categories: list) -> str:
    total = sum(len(c["prompts"]) for c in categories)
    parts = []
    parts.append('<div class="wrap">')
    parts.append('<header class="masthead">')
    parts.append('<p class="kicker">PromptDrawer</p>')
    parts.append("<h1>50 AI Prompts for Solo &amp; Small-Business Operators</h1>")
    parts.append(
        '<p class="sub">Paste-ready prompts for the jobs that land on one person: '
        "marketing, sales, support, content, admin, money, hiring.</p>"
    )
    parts.append(
        f'<p class="meta">Version {PACK_VERSION} &middot; {PACK_DATE} &middot; '
        f"{total} prompts in {len(categories)} categories &middot; "
        "no accounts, no software, nothing to install</p>"
    )
    parts.append("</header>")

    parts.append('<section class="intro">')
    parts.append("<h2>How to use this pack</h2>")
    parts.append(
        "<p>Each prompt is built the same way: a line telling you when to use it, the full "
        "prompt text to copy, a list of the placeholders to fill in, and a tip for what to "
        "do with the answer.</p>"
    )
    parts.append("<ol>")
    parts.append("<li>Find the prompt that fits the job you have right now, using the list below.</li>")
    parts.append(
        "<li>Replace every <span class=\"ph\">[SQUARE BRACKET]</span> with your own details. "
        "Delete placeholders that do not apply rather than leaving them in.</li>"
    )
    parts.append("<li>Paste the whole thing into an AI assistant (ChatGPT, Claude, Gemini, Copilot &mdash; any of them).</li>")
    parts.append(
        "<li>Read the answer critically. The prompts tell the assistant to work from what you "
        "gave it and to ask you questions instead of inventing facts, but you know your "
        "business best.</li>"
    )
    parts.append("<li>If the answer is close but not right, use the follow-up line in the tip instead of starting again.</li>")
    parts.append("</ol>")
    parts.append("<h3>What is not claimed here</h3>")
    parts.append(
        "<p>This is a set of written prompts: not a course, not software, not a subscription. "
        "It makes no promise about results, savings, revenue or time, because nobody has "
        "measured those for this pack. What is true is narrow and checkable &mdash; there are "
        "50 prompts, each is paste-ready, every placeholder is marked and explained, and each "
        "carries a tip.</p>"
    )
    parts.append("</section>")

    parts.append('<nav class="toc">')
    parts.append(f"<h2>Contents &mdash; {total} prompts</h2>")
    parts.append("<ol>")
    for index, category in enumerate(categories):
        count = len(category["prompts"])
        parts.append("<li>")
        parts.append(f'<a href="#{anchor(index)}">{esc(category["category"])}</a> ({count})')
        parts.append("<ol>")
        for prompt in category["prompts"]:
            parts.append(f'<li>{prompt["number"]}. {esc(prompt["title"])}</li>')
        parts.append("</ol>")
        parts.append("</li>")
    parts.append("</ol>")
    parts.append("</nav>")

    for index, category in enumerate(categories):
        count = len(category["prompts"])
        parts.append(f'<section class="cat" id="{anchor(index)}">')
        parts.append(f"<h2>{esc(category['category'])}</h2>")
        parts.append(f'<p class="count">{count} prompt{"s" if count != 1 else ""}</p>')
        if category["intro"]:
            parts.append(f'<p class="catintro">{esc(category["intro"])}</p>')
        for prompt in category["prompts"]:
            parts.append('<article class="prompt">')
            parts.append(f'<h3><span class="num">{prompt["number"]}.</span> {esc(prompt["title"])}</h3>')
            parts.append(f'<p class="when"><strong>When to use:</strong> {esc(prompt["when"])}</p>')
            parts.append(f'<div class="prompttext">{mark_placeholders(esc(prompt["prompt"]))}</div>')
            parts.append('<div class="fill"><strong>Fill in</strong><ul>')
            for label, meaning in prompt["fills"]:
                parts.append(f"<li>{inline_code(label)} &mdash; {esc(meaning)}</li>")
            parts.append("</ul></div>")
            if prompt["note"]:
                parts.append(f'<p class="note"><strong>Note:</strong> {esc(prompt["note"])}</p>')
            parts.append(f'<p class="tip"><strong>Tip:</strong> {esc(prompt["tip"])}</p>')
            parts.append("</article>")
        parts.append("</section>")

    parts.append("<footer>")
    parts.append(
        f"<p>{PACK_TITLE} &mdash; 50 AI prompts for solo and small-business operators. "
        f"Version {PACK_VERSION}, {PACK_DATE}.</p>"
    )
    parts.append(
        "<p>Written for people running a business on their own. The prompts are text you paste "
        "into an AI assistant you already have; this file contains everything needed to use "
        "them and loads nothing from the internet.</p>"
    )
    parts.append("</footer>")
    parts.append("</div>")
    return "\n".join(parts)


def build_html(categories: list) -> str:
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>PromptDrawer - 50 AI Prompts for Solo &amp; Small-Business Operators</title>\n"
        '<meta name="description" content="50 paste-ready AI prompts for solo and small-business operators, in 8 categories, each with placeholders explained and a tip.">\n'
        "<style>\n" + CSS.strip() + "\n</style>\n</head>\n<body>\n" + build_html_body(categories) + "\n</body>\n</html>\n"
    )


def main() -> int:
    check_only = "--check" in sys.argv[1:]
    try:
        categories = load_pack()
    except SourceError as error:
        print(f"BUILD FAILED: {error}", file=sys.stderr)
        return 1

    total = sum(len(c["prompts"]) for c in categories)
    markdown = build_markdown(categories)
    webpage = build_html(categories)

    if check_only:
        stale = [
            path.name
            for path, fresh in ((OUT_MD, markdown), (OUT_HTML, webpage))
            if not path.exists() or path.read_text(encoding="utf-8") != fresh
        ]
        if stale:
            print(
                f"OUT OF DATE: {', '.join(stale)} - re-run python3 tools/build_pack.py",
                file=sys.stderr,
            )
            return 1
        print(f"Up to date: {total} prompts, {len(categories)} categories, both files match the sources")
        return 0

    OUT_MD.write_text(markdown, encoding="utf-8")
    OUT_HTML.write_text(webpage, encoding="utf-8")
    print(f"Built {OUT_MD.name} and {OUT_HTML.name}: {total} prompts, {len(categories)} categories")
    for category in categories:
        print(f"  {len(category['prompts']):>2}  {category['category']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
