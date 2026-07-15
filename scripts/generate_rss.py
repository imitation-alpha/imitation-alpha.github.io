#!/usr/bin/env python3
"""Generate RSS 2.0 feeds for the static blog."""

from __future__ import annotations

import html
import re
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from email.utils import format_datetime
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE_URL = "https://imitation-alpha.github.io/"
AUTHOR = "Arthur Yau"
FEED_TITLE = "arthuryau's blog RSS"
HYL_FEED_TITLE = "arthuryau's Lee Hung-yi-inspired teaching-style RSS"
DC_NS = "http://purl.org/dc/elements/1.1/"

ET.register_namespace("dc", DC_NS)


@dataclass(frozen=True)
class Post:
    title: str
    description: str
    url: str
    published: date
    author: str


class PostHeadParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.html_lang = ""
        self.title_text = ""
        self._in_title = False
        self.meta: dict[str, str] = {}
        self.links: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): value or "" for key, value in attrs}
        if tag == "html":
            self.html_lang = attr.get("lang", "")
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = attr.get("property") or attr.get("name")
            content = attr.get("content", "")
            if key and content:
                self.meta[key] = content
        elif tag == "link":
            self.links.append(attr)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_text += data


def parse_post(path: Path, language: str) -> Post:
    parser = PostHeadParser()
    parser.feed(path.read_text(encoding="utf-8"))

    title = parser.meta.get("og:title") or parser.title_text.replace(" — Arthur", "")
    description = parser.meta.get("description") or parser.meta.get("og:description", "")
    published_text = parser.meta.get("article:published_time")
    if not title or not description or not published_text:
        raise ValueError(f"{path} is missing title, description, or published date metadata")

    author = parser.meta.get("article:author") or parser.meta.get("author") or AUTHOR
    url = find_absolute_url(parser.links, path, language)
    return Post(
        title=html.unescape(title),
        description=html.unescape(description),
        url=url,
        published=date.fromisoformat(published_text[:10]),
        author=html.unescape(author),
    )


def find_absolute_url(links: list[dict[str, str]], path: Path, language: str) -> str:
    for link in links:
        if link.get("rel") == "canonical" and link.get("href", "").startswith(SITE_URL):
            return link["href"]

    for link in links:
        if (
            link.get("rel") == "alternate"
            and link.get("hreflang") == language
            and link.get("href", "").startswith(SITE_URL)
        ):
            return link["href"]

    return SITE_URL + path.relative_to(ROOT).as_posix()


def post_files(directory: Path) -> list[Path]:
    files = {path.name: path for path in directory.glob("*.html") if path.name != "index.html"}
    index_html = (directory / "index.html").read_text(encoding="utf-8")
    ordered_names = [
        href
        for href in re.findall(r'<a\b[^>]*\bhref="([^"]+\.html)"[^>]*>', index_html)
        if href in files
    ]

    ordered = []
    seen = set()
    for name in ordered_names:
        if name not in seen:
            ordered.append(files[name])
            seen.add(name)

    ordered.extend(files[name] for name in sorted(files) if name not in seen)
    return ordered


def format_pubdate(value: date) -> str:
    dt = datetime.combine(value, time.min, timezone.utc)
    return format_datetime(dt)


def write_feed(path: Path, channel: dict[str, str], posts: list[Post]) -> None:
    rss = ET.Element("rss", {"version": "2.0"})
    channel_el = ET.SubElement(rss, "channel")
    ET.SubElement(channel_el, "title").text = channel["title"]
    ET.SubElement(channel_el, "link").text = channel["link"]
    ET.SubElement(channel_el, "description").text = channel["description"]
    ET.SubElement(channel_el, "language").text = channel["language"]
    ET.SubElement(channel_el, "lastBuildDate").text = format_pubdate(posts[0].published)

    for post in posts:
        item = ET.SubElement(channel_el, "item")
        ET.SubElement(item, "title").text = post.title
        ET.SubElement(item, "link").text = post.url
        guid = ET.SubElement(item, "guid", {"isPermaLink": "true"})
        guid.text = post.url
        ET.SubElement(item, "description").text = post.description
        ET.SubElement(item, "pubDate").text = format_pubdate(post.published)
        ET.SubElement(item, f"{{{DC_NS}}}creator").text = post.author

    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ")
    path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(path, encoding="utf-8", xml_declaration=True, short_empty_elements=False)


def collect_posts(directory: Path, language: str) -> list[Post]:
    posts = [parse_post(path, language) for path in post_files(directory)]
    return sorted(posts, key=lambda post: post.published, reverse=True)


def main() -> None:
    english_posts = collect_posts(ROOT / "blog", "en")
    english_hyl_posts = collect_posts(ROOT / "en-hyl" / "blog", "en-x-hyl")
    zh_posts = collect_posts(ROOT / "zh-Hant" / "blog", "zh-Hant")

    write_feed(
        ROOT / "blog" / "feed.xml",
        {
            "title": FEED_TITLE,
            "link": SITE_URL + "blog/",
            "description": "Notes on agentic systems, ML infrastructure, and tooling.",
            "language": "en",
        },
        english_posts,
    )
    shutil.copyfile(ROOT / "blog" / "feed.xml", ROOT / "feed.xml")

    write_feed(
        ROOT / "en-hyl" / "blog" / "feed.xml",
        {
            "title": HYL_FEED_TITLE,
            "link": SITE_URL + "en-hyl/blog/",
            "description": (
                "English posts rewritten with a roadmap-first, intuition-before-mechanism "
                "teaching flow inspired by Lee Hung-yi. These posts were not written, "
                "reviewed, or endorsed by Lee Hung-yi."
            ),
            "language": "en-x-hyl",
        },
        english_hyl_posts,
    )

    write_feed(
        ROOT / "zh-Hant" / "blog" / "feed.xml",
        {
            "title": FEED_TITLE,
            "link": SITE_URL + "zh-Hant/blog/",
            "description": "關於 agentic systems、ML infrastructure 與 tooling 的繁體中文筆記。",
            "language": "zh-Hant",
        },
        zh_posts,
    )


if __name__ == "__main__":
    main()
