#!/usr/bin/env python3
"""Build a per-item Atom feed from Horizon daily summaries.

Each news item inside a daily digest becomes its own feed entry so readers
like Folo can show them as a timeline instead of one long post per day.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import re
from datetime import datetime, timedelta
from pathlib import Path

try:
    import markdown as _markdown
except ImportError:  # local testing without the project venv
    _markdown = None


def to_html(text: str) -> str:
    if _markdown is not None:
        return _markdown.markdown(text, extensions=["extra", "sane_lists"])
    blocks = []
    for para in re.split(r"\n{2,}", text.strip()):
        if para.startswith("<"):
            blocks.append(para)
        else:
            blocks.append("<p>" + html.escape(para).replace("\n", "<br/>") + "</p>")
    return "\n".join(blocks)

FRONT_MATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)
ITEM_START = re.compile(r'<a id="item-([^"]+)"></a>\s*\n### \[(.+?)\]\((.*?)\)')
DATE_LINE = re.compile(r"^date:\s*(\d{4}-\d{2}-\d{2})", re.M)
SITE_URL = "https://sjtonghero-collab.github.io/Horizon"


def parse_post(path: Path) -> tuple[str, list[dict]]:
    text = path.read_text(encoding="utf-8")
    match = FRONT_MATTER.match(text)
    front = match.group(1) if match else ""
    body = text[match.end():] if match else text

    date_match = DATE_LINE.search(front)
    date = date_match.group(1) if date_match else path.stem[:10]

    items: list[dict] = []
    starts = list(ITEM_START.finditer(body))
    for idx, found in enumerate(starts):
        end = starts[idx + 1].start() if idx + 1 < len(starts) else len(body)
        chunk = body[found.end():end].strip()
        chunk = re.split(r"\n-{3,}\s*$", chunk)[0].strip()
        title = found.group(2).strip()
        url = found.group(3).strip()
        if not title:
            continue
        items.append({"title": title, "url": url, "markdown": chunk, "date": date})
    return date, items


def build(posts_dir: Path, out: Path, days: int, limit: int) -> int:
    posts = sorted(posts_dir.glob("*-summary-zh.md"), key=lambda p: p.name, reverse=True)[:days]
    collected: list[dict] = []
    for path in posts:
        _, items = parse_post(path)
        collected.extend(items)

    entries = []
    for idx, item in enumerate(collected[:limit]):
        try:
            base = datetime.strptime(item["date"], "%Y-%m-%d")
        except ValueError:
            base = datetime.utcnow()
        stamp = base + timedelta(minutes=len(collected) - idx)
        body_html = to_html(item["markdown"])
        if item["url"]:
            body_html += f'<p><a href="{html.escape(item["url"])}">阅读原文</a></p>'
        link = item["url"] or f"{SITE_URL}/{item['date'].replace('-', '/')}/summary-zh.html"
        entry_id = hashlib.sha1((item["title"] + link).encode()).hexdigest()
        entries.append(
            "<entry>\n"
            f"  <title>{html.escape(item['title'])}</title>\n"
            f'  <link href="{html.escape(link)}"/>\n'
            f"  <id>urn:horizon:{entry_id}</id>\n"
            f"  <updated>{stamp.strftime('%Y-%m-%dT%H:%M:%SZ')}</updated>\n"
            f'  <content type="html"><![CDATA[{body_html}]]></content>\n'
            "</entry>"
        )

    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<feed xmlns="http://www.w3.org/2005/Atom">\n'
        "  <title>Horizon 新闻雷达 · 逐条</title>\n"
        f'  <link href="{SITE_URL}/feed-items.xml" rel="self"/>\n'
        f'  <link href="{SITE_URL}/"/>\n'
        f"  <updated>{now}</updated>\n"
        f"  <id>{SITE_URL}/feed-items.xml</id>\n"
        "  <author><name>Horizon</name></author>\n"
        + "\n".join(entries)
        + "\n</feed>\n"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(xml, encoding="utf-8")
    return len(entries)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--posts-dir", default="docs/_posts")
    parser.add_argument("--out", default="docs/feed-items.xml")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()
    count = build(Path(args.posts_dir), Path(args.out), args.days, args.limit)
    print(f"feed-items.xml written with {count} entries")


if __name__ == "__main__":
    main()
