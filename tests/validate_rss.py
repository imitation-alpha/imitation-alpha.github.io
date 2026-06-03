#!/usr/bin/env python3
"""Validate committed RSS feeds and autodiscovery links."""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
SITE_URL = "https://imitation-alpha.github.io/"
FEED_TITLE = "arthuryau's blog RSS"
DC_NS = "http://purl.org/dc/elements/1.1/"

FEEDS = {
    "feed.xml": {
        "language": "en",
        "source_dir": ROOT / "blog",
        "channel_link": SITE_URL + "blog/",
    },
    "blog/feed.xml": {
        "language": "en",
        "source_dir": ROOT / "blog",
        "channel_link": SITE_URL + "blog/",
    },
    "zh-Hant/blog/feed.xml": {
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
    urls = []
    for href in re.findall(r'<a href="([^"]+\.html)">', index_html):
        if href == "index.html":
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
    if channel.findtext("title") != FEED_TITLE:
        fail(f"{path_text} channel title must be {FEED_TITLE!r}")

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


def expected_feed_path(page_path: Path) -> Path:
    relative = page_path.relative_to(ROOT).as_posix()
    if relative == "index.html":
        return ROOT / "feed.xml"
    if relative.startswith("zh-Hant/blog/"):
        return ROOT / "zh-Hant" / "blog" / "feed.xml"
    if relative.startswith("blog/"):
        return ROOT / "blog" / "feed.xml"
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
        ROOT / "zh-Hant" / "blog" / "index.html",
        *sorted((ROOT / "blog").glob("*.html")),
        *sorted((ROOT / "zh-Hant" / "blog").glob("*.html")),
    ]
    html_paths = sorted(set(html_paths))

    rss_link_pattern = re.compile(
        r'<link\s+rel="alternate"\s+type="application/rss\+xml"\s+'
        r'title="([^"]+)"\s+href="([^"]*feed\.xml)"\s*/>'
    )

    missing = []
    for path in html_paths:
        text = path.read_text(encoding="utf-8")
        matches = rss_link_pattern.findall(text)
        expected_path = expected_feed_path(path).resolve()
        matching_links = [
            (title, href)
            for title, href in matches
            if title == FEED_TITLE and resolve_feed_href(path, href) == expected_path
        ]
        if not matching_links:
            missing.append(str(path.relative_to(ROOT)))

    if missing:
        fail("missing RSS autodiscovery links in: " + ", ".join(missing))


def main() -> None:
    for path_text, config in FEEDS.items():
        validate_feed(path_text, config)
    validate_feed_alias()
    validate_autodiscovery_links()
    print("RSS validation passed")


if __name__ == "__main__":
    main()
