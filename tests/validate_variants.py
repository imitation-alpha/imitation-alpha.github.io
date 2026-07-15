#!/usr/bin/env python3
"""Validate blog variant clusters, indexes, navigation, and local assets."""

from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
SITE_URL = "https://imitation-alpha.github.io/"

POST_ORDER = [
    "loop-engineering.html",
    "recursive-self-improving-ai-rubicon.html",
    "ai-self-correction-decoding-workflow-reasoning.html",
    "ai-agent-harness-engineering.html",
    "ai-agent-research-work.html",
    "ai-agent-multi-agent-interaction.html",
    "ai-agent-context-engineering.html",
    "ai-agent-systems-hung-yi-lee-summary.html",
    "orchestrating-coding-agents.html",
]

VARIANTS = {
    "en": ROOT / "blog",
    "en-x-hyl": ROOT / "en-hyl" / "blog",
    "zh-Hant": ROOT / "zh-Hant" / "blog",
    "zh-Hant-x-hyl": ROOT / "zh-Hant-hyl" / "blog",
}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.html_lang = ""
        self.title = ""
        self._in_title = False
        self.links: list[dict[str, str]] = []
        self.anchors: list[dict[str, str]] = []
        self.footer_anchors: list[dict[str, str]] = []
        self.footer_slots: dict[str, list[dict[str, str]]] = {"previous": [], "next": []}
        self.resource_urls: list[str] = []
        self.ids: set[str] = set()
        self.duplicate_ids: set[str] = set()
        self.fragment_hrefs: list[str] = []
        self.text_parts: list[str] = []
        self._in_post_footer = False
        self._footer_slot = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): value or "" for key, value in attrs}
        element_id = attr.get("id")
        if element_id:
            if element_id in self.ids:
                self.duplicate_ids.add(element_id)
            self.ids.add(element_id)

        if tag == "html":
            self.html_lang = attr.get("lang", "")
        elif tag == "title":
            self._in_title = True
        elif tag == "link":
            self.links.append(attr)
            if attr.get("href"):
                self.resource_urls.append(attr["href"])
        elif tag == "footer" and "post__footer" in attr.get("class", "").split():
            self._in_post_footer = True
        elif tag == "li" and self._in_post_footer:
            classes = attr.get("class", "").split()
            if "post__nav__item--previous" in classes:
                self._footer_slot = "previous"
            elif "post__nav__item--next" in classes:
                self._footer_slot = "next"
        elif tag == "a":
            self.anchors.append(attr)
            if self._in_post_footer:
                self.footer_anchors.append(attr)
                if self._footer_slot:
                    self.footer_slots[self._footer_slot].append(attr)
            href = attr.get("href", "")
            if href:
                self.resource_urls.append(href)
                if href.startswith("#"):
                    self.fragment_hrefs.append(href[1:])
        elif tag in {"img", "script"} and attr.get("src"):
            self.resource_urls.append(attr["src"])

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "footer" and self._in_post_footer:
            self._in_post_footer = False
            self._footer_slot = ""
        elif tag == "li" and self._in_post_footer:
            self._footer_slot = ""

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if data.strip():
            self.text_parts.append(data.strip())

    @property
    def text(self) -> str:
        return " ".join(self.text_parts)


def parse_page(path: Path) -> PageParser:
    parser = PageParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def resolve_target(page_path: Path, value: str) -> Path | None:
    if value.startswith("//"):
        return None
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        if not value.startswith(SITE_URL):
            return None
        return (ROOT / unquote(parsed.path).lstrip("/")).resolve()
    path_text = unquote(parsed.path)
    if not path_text:
        return page_path.resolve()
    if path_text.startswith("/"):
        return (ROOT / path_text.lstrip("/")).resolve()
    return (page_path.parent / path_text).resolve()


def site_url(path: Path) -> str:
    return SITE_URL + path.relative_to(ROOT).as_posix()


def main() -> None:
    failures: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            failures.append(message)

    expected_names = set(POST_ORDER)
    parsed_pages: dict[Path, PageParser] = {}

    for language, directory in VARIANTS.items():
        actual_names = {path.name for path in directory.glob("*.html") if path.name != "index.html"}
        check(
            actual_names == expected_names,
            f"{directory.relative_to(ROOT)} article set differs: "
            f"missing={sorted(expected_names - actual_names)}, extra={sorted(actual_names - expected_names)}",
        )

        index_path = directory / "index.html"
        index = parse_page(index_path)
        parsed_pages[index_path] = index
        indexed_targets = [
            resolve_target(index_path, anchor.get("href", ""))
            for anchor in index.anchors
            if Path(urlparse(anchor.get("href", "")).path).name in expected_names
        ]
        expected_index_targets = [(directory / slug).resolve() for slug in POST_ORDER]
        check(
            indexed_targets == expected_index_targets,
            f"{index_path.relative_to(ROOT)} post order/targets do not match the collection",
        )

        for slug in POST_ORDER:
            page_path = directory / slug
            if not page_path.exists():
                continue
            page = parse_page(page_path)
            parsed_pages[page_path] = page
            check(
                page.html_lang == language,
                f"{page_path.relative_to(ROOT)} lang={page.html_lang!r}, expected {language!r}",
            )

            canonical_links = [link for link in page.links if link.get("rel") == "canonical"]
            check(
                len(canonical_links) == 1 and canonical_links[0].get("href") == site_url(page_path),
                f"{page_path.relative_to(ROOT)} must have one self canonical",
            )

            alternates = {
                link.get("hreflang", ""): link.get("href", "")
                for link in page.links
                if link.get("rel") == "alternate" and link.get("hreflang")
            }
            expected_alternates = {
                variant: site_url(variant_dir / slug)
                for variant, variant_dir in VARIANTS.items()
            }
            expected_alternates["x-default"] = site_url(VARIANTS["en"] / slug)
            for alternate_language, expected_url in expected_alternates.items():
                check(
                    alternates.get(alternate_language) == expected_url,
                    f"{page_path.relative_to(ROOT)} has incorrect {alternate_language} alternate",
                )

            anchor_targets = {
                target
                for anchor in page.anchors
                if (target := resolve_target(page_path, anchor.get("href", ""))) is not None
            }
            for sibling_language, sibling_dir in VARIANTS.items():
                sibling_path = (sibling_dir / slug).resolve()
                if sibling_language != language:
                    check(
                        sibling_path in anchor_targets,
                        f"{page_path.relative_to(ROOT)} does not visibly link {sibling_language}",
                    )

            for fragment in page.fragment_hrefs:
                check(
                    fragment in page.ids,
                    f"{page_path.relative_to(ROOT)} links missing fragment #{fragment}",
                )
            check(
                not page.duplicate_ids,
                f"{page_path.relative_to(ROOT)} has duplicate IDs: {sorted(page.duplicate_ids)}",
            )

            if language == "en-x-hyl":
                check(
                    "Lee Hung-yi-inspired teaching style" in page.title,
                    f"{page_path.relative_to(ROOT)} title does not identify the teaching-style variant",
                )
                lowered_text = page.text.lower()
                check(
                    all(phrase in lowered_text for phrase in ("not written", "reviewed", "endorsed")),
                    f"{page_path.relative_to(ROOT)} is missing the visible non-endorsement disclaimer",
                )

    for language in ("en-x-hyl", "zh-Hant-x-hyl"):
        directory = VARIANTS[language]
        for index, slug in enumerate(POST_ORDER):
            page_path = directory / slug
            if not page_path.exists():
                continue
            page = parsed_pages[page_path]
            actual_newer = [
                target
                for anchor in page.footer_slots["previous"]
                if (target := resolve_target(page_path, anchor.get("href", ""))) is not None
            ]
            actual_older = [
                target
                for anchor in page.footer_slots["next"]
                if (target := resolve_target(page_path, anchor.get("href", ""))) is not None
            ]
            expected_newer = [(directory / POST_ORDER[index - 1]).resolve()] if index > 0 else []
            expected_older = (
                [(directory / POST_ORDER[index + 1]).resolve()]
                if index + 1 < len(POST_ORDER)
                else []
            )
            check(
                actual_newer == expected_newer and actual_older == expected_older,
                f"{page_path.relative_to(ROOT)} newer/older navigation leaves its collection or is in the wrong slot",
            )

    pages_to_check = {ROOT / "index.html", *parsed_pages.keys()}
    for page_path in sorted(pages_to_check):
        page = parsed_pages.get(page_path) or parse_page(page_path)
        for value in page.resource_urls:
            target = resolve_target(page_path, value)
            if target is None:
                continue
            try:
                target.relative_to(ROOT.resolve())
            except ValueError:
                failures.append(f"{page_path.relative_to(ROOT)} links outside the site: {value}")
                continue
            check(
                target.exists(),
                f"{page_path.relative_to(ROOT)} has missing local target {value}",
            )

    if failures:
        print("Variant validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        raise SystemExit(1)

    print("Blog variant validation passed")


if __name__ == "__main__":
    main()
