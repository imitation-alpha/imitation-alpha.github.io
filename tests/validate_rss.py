#!/usr/bin/env python3
"""Validate committed RSS feeds and autodiscovery links."""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
SITE_URL = "https://imitation-alpha.github.io/"
FEED_TITLE = "arthuryau's blog RSS"
HYL_FEED_TITLE = "arthuryau's Lee Hung-yi-inspired teaching-style RSS"
DC_NS = "http://purl.org/dc/elements/1.1/"

FEEDS = {
    "feed.xml": {
        "title": FEED_TITLE,
        "language": "en",
        "source_dir": ROOT / "blog",
        "channel_link": SITE_URL + "blog/",
    },
    "blog/feed.xml": {
        "title": FEED_TITLE,
        "language": "en",
        "source_dir": ROOT / "blog",
        "channel_link": SITE_URL + "blog/",
    },
    "en-hyl/blog/feed.xml": {
        "title": HYL_FEED_TITLE,
        "language": "en-x-hyl",
        "source_dir": ROOT / "en-hyl" / "blog",
        "channel_link": SITE_URL + "en-hyl/blog/",
        "description_phrases": ("not written", "reviewed", "endorsed"),
    },
    "zh-Hant/blog/feed.xml": {
        "title": FEED_TITLE,
        "language": "zh-Hant",
        "source_dir": ROOT / "zh-Hant" / "blog",
        "channel_link": SITE_URL + "zh-Hant/blog/",
    },
}


def fail(message: str) -> None:
    print(f"RSS validation failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def expected_post_count(source_dir: Path) -> int:
    return len([p for p in source_dir.glob("*.html") if p.name != "index.html"])


def absolute_url(value: str) -> bool:
    return value.startswith(SITE_URL) and not value.startswith(SITE_URL + "/")


def index_post_urls(source_dir: Path) -> list[str]:
    index_html = (source_dir / "index.html").read_text(encoding="utf-8")
    post_names = {path.name for path in source_dir.glob("*.html") if path.name != "index.html"}
    urls = []
    for href in re.findall(r'<a\b[^>]*\bhref="([^"]+\.html)"[^>]*>', index_html):
        if href not in post_names:
            continue
        urls.append(SITE_URL + (source_dir / href).relative_to(ROOT).as_posix())
    return urls


def validate_feed(path_text: str, config: dict[str, object]) -> None:
    path = ROOT / path_text
    if not path.exists():
        fail(f"missing feed {path_text}")

    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        fail(f"{path_text} is not valid XML: {exc}")

    root = tree.getroot()
    if root.tag != "rss" or root.attrib.get("version") != "2.0":
        fail(f"{path_text} root must be <rss version=\"2.0\">")

    channel = root.find("channel")
    if channel is None:
        fail(f"{path_text} is missing channel")

    language = channel.findtext("language")
    if language != config["language"]:
        fail(f"{path_text} language is {language!r}, expected {config['language']!r}")

    link = channel.findtext("link")
    if link != config["channel_link"]:
        fail(f"{path_text} channel link is {link!r}, expected {config['channel_link']!r}")

    for tag in ("title", "description", "lastBuildDate"):
        if not (channel.findtext(tag) or "").strip():
            fail(f"{path_text} channel is missing {tag}")
    if channel.findtext("title") != config["title"]:
        fail(f"{path_text} channel title must be {config['title']!r}")
    description = (channel.findtext("description") or "").lower()
    for phrase in config.get("description_phrases", ()):  # type: ignore[union-attr]
        if phrase not in description:
            fail(f"{path_text} channel description is missing {phrase!r}")

    items = channel.findall("item")
    expected_count = expected_post_count(config["source_dir"])  # type: ignore[arg-type]
    if len(items) != expected_count:
        fail(f"{path_text} has {len(items)} items, expected {expected_count}")

    dates = []
    item_links = []
    for item in items:
        for tag in ("title", "description", "link", "guid", "pubDate"):
            if not (item.findtext(tag) or "").strip():
                fail(f"{path_text} item is missing {tag}")
        if not (item.findtext(f"{{{DC_NS}}}creator") or "").strip():
            fail(f"{path_text} item is missing dc:creator")

        item_link = item.findtext("link") or ""
        item_links.append(item_link)
        guid = item.findtext("guid") or ""
        if not absolute_url(item_link):
            fail(f"{path_text} item link is not an absolute site URL: {item_link!r}")
        if guid != item_link:
            fail(f"{path_text} item guid {guid!r} must match link {item_link!r}")

        try:
            dates.append(parsedate_to_datetime(item.findtext("pubDate") or ""))
        except (TypeError, ValueError) as exc:
            fail(f"{path_text} item pubDate is not RFC 2822 parseable: {exc}")

    if dates != sorted(dates, reverse=True):
        fail(f"{path_text} items are not sorted newest first")

    expected_urls = index_post_urls(config["source_dir"])  # type: ignore[arg-type]
    if item_links != expected_urls:
        fail(f"{path_text} item order must match the blog index order")


def validate_feed_alias() -> None:
    site_feed = (ROOT / "feed.xml").read_text(encoding="utf-8")
    blog_feed = (ROOT / "blog" / "feed.xml").read_text(encoding="utf-8")
    if site_feed != blog_feed:
        fail("feed.xml must match blog/feed.xml exactly")


class FeedLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "link":
            return
        attr = {key.lower(): value or "" for key, value in attrs}
        if attr.get("rel") == "alternate" and attr.get("type") == "application/rss+xml":
            self.links.append(attr)


def expected_feeds(page_path: Path) -> dict[Path, str]:
    relative = page_path.relative_to(ROOT).as_posix()
    if relative == "index.html":
        return {
            ROOT / "feed.xml": FEED_TITLE,
            ROOT / "en-hyl" / "blog" / "feed.xml": HYL_FEED_TITLE,
        }
    if relative == "blog/index.html":
        return {
            ROOT / "blog" / "feed.xml": FEED_TITLE,
            ROOT / "en-hyl" / "blog" / "feed.xml": HYL_FEED_TITLE,
        }
    if relative.startswith("en-hyl/blog/"):
        return {ROOT / "en-hyl" / "blog" / "feed.xml": HYL_FEED_TITLE}
    if relative.startswith("zh-Hant/blog/"):
        return {ROOT / "zh-Hant" / "blog" / "feed.xml": FEED_TITLE}
    if relative.startswith("zh-Hant-hyl/blog/"):
        return {ROOT / "blog" / "feed.xml": FEED_TITLE}
    if relative.startswith("blog/"):
        return {ROOT / "blog" / "feed.xml": FEED_TITLE}
    fail(f"no expected feed path for {relative}")


def resolve_feed_href(page_path: Path, href: str) -> Path:
    parsed = urlparse(href)
    if parsed.scheme or parsed.netloc:
        if href.startswith(SITE_URL):
            return ROOT / parsed.path.lstrip("/")
        fail(f"{page_path.relative_to(ROOT)} has external feed href {href!r}")
    return (page_path.parent / href).resolve()


def validate_autodiscovery_links() -> None:
    html_paths = [
        ROOT / "index.html",
        ROOT / "blog" / "index.html",
        ROOT / "en-hyl" / "blog" / "index.html",
        ROOT / "zh-Hant" / "blog" / "index.html",
        ROOT / "zh-Hant-hyl" / "blog" / "index.html",
        *sorted((ROOT / "blog").glob("*.html")),
        *sorted((ROOT / "en-hyl" / "blog").glob("*.html")),
        *sorted((ROOT / "zh-Hant" / "blog").glob("*.html")),
        *sorted((ROOT / "zh-Hant-hyl" / "blog").glob("*.html")),
    ]
    html_paths = sorted(set(html_paths))

    mismatches = []
    for path in html_paths:
        parser = FeedLinkParser()
        parser.feed(path.read_text(encoding="utf-8"))
        links = {
            (resolve_feed_href(path, link.get("href", "")), link.get("title", ""))
            for link in parser.links
        }
        expected_links = {
            (expected_path.resolve(), expected_title)
            for expected_path, expected_title in expected_feeds(path).items()
        }
        if links != expected_links:
            mismatches.append(str(path.relative_to(ROOT)))

    if mismatches:
        fail("incorrect RSS autodiscovery links in: " + ", ".join(mismatches))


def main() -> None:
    for path_text, config in FEEDS.items():
        validate_feed(path_text, config)
    validate_feed_alias()
    validate_autodiscovery_links()
    print("RSS validation passed")


if __name__ == "__main__":
    main()
