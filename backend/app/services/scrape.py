"""Lightweight summerhouse-page scraping.

The fetch is split from the parse so that parse_summerhouse_html can be unit-tested
in isolation without network or HTTP mocking.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

DEFAULT_TIMEOUT_SECONDS = 8.0
USER_AGENT = "KarkovWeekend/1.0 (+https://karkovweekend.dk)"


@dataclass
class SummerhouseSummary:
    title: str | None
    summary: str | None
    image_url: str | None


def _meta(soup: BeautifulSoup, *names: str) -> str | None:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find(
            "meta", attrs={"name": name}
        )
        if tag is None:
            continue
        content = tag.get("content")
        if content:
            return content.strip()
    return None


def _first_text(soup: BeautifulSoup, *selectors: str) -> str | None:
    for sel in selectors:
        el = soup.select_one(sel)
        if el is not None:
            text = el.get_text(strip=True)
            if text:
                return text
    return None


_GENERIC_SUMMARY_HINTS = (
    "nyhedsbrev",
    "newsletter",
    "tilmeld dig",
    "subscribe",
    "cookie",
    "privatliv",
    "log ind",
    "log on",
    "sign up",
    "rabat",
)


def _looks_generic(text: str) -> bool:
    """Detect og:description / meta-description blurbs that aren't about the listing.

    Booking sites (Novasol, DanCenter, etc.) often serve site-wide marketing copy
    in og:description; we'd rather show the first descriptive paragraph instead.
    """
    if len(text) < 60:
        return True
    lower = text.lower()
    return any(h in lower for h in _GENERIC_SUMMARY_HINTS)


def _first_long_paragraph(soup: BeautifulSoup, *, min_len: int = 60) -> str | None:
    for p in soup.find_all("p"):
        text = p.get_text(" ", strip=True)
        if len(text) >= min_len and not _looks_generic(text):
            return text
    return None


def parse_summerhouse_html(html: str, base_url: str) -> SummerhouseSummary:
    soup = BeautifulSoup(html, "html.parser")

    title = (
        _meta(soup, "og:title", "twitter:title")
        or _first_text(soup, "h1")
        or (soup.title.get_text(strip=True) if soup.title else None)
    )

    meta_summary = _meta(soup, "og:description", "twitter:description", "description")
    para_summary = _first_long_paragraph(soup)
    if meta_summary is None or _looks_generic(meta_summary):
        summary = para_summary or meta_summary
    else:
        summary = meta_summary
    if summary:
        summary = summary[:600]

    image_url = _meta(soup, "og:image", "twitter:image")
    if image_url is None:
        img = soup.find("img", src=True)
        if img is not None:
            image_url = img["src"]
    if image_url:
        image_url = urljoin(base_url, image_url)

    return SummerhouseSummary(title=title, summary=summary, image_url=image_url)


def fetch_summerhouse(url: str, *, client: httpx.Client | None = None) -> SummerhouseSummary:
    if not url.startswith(("http://", "https://")):
        raise ValueError("URL skal starte med http:// eller https://")
    own_client = client is None
    if client is None:
        client = httpx.Client(
            timeout=DEFAULT_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
    try:
        resp = client.get(url)
        resp.raise_for_status()
        return parse_summerhouse_html(resp.text, str(resp.url))
    finally:
        if own_client:
            client.close()
