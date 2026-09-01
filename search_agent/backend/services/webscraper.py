"""Utilities for scraping unofficial public discussion sources."""

from __future__ import annotations

import re
from typing import Iterable

import requests
from bs4 import BeautifulSoup


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-SG,en;q=0.9",
}


def clean_text(value: str) -> str:
    """Normalise whitespace in extracted text."""
    return re.sub(r"\s+", " ", value or "").strip()


def source_label(url: str) -> str:
    """Return a simple source label for a given URL."""
    host = url.lower()

    if "reddit.com" in host:
        return "Reddit Singapore"
    if "hardwarezone.com" in host:
        return "HardwareZone"
    if "facebook.com" in host or "fb.com" in host:
        return "Facebook public page"
    return "Unofficial forum"


def fetch_page(url: str) -> str:
    """Fetch a page and return its raw HTML."""
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
    response.raise_for_status()
    return response.text


def extract_content_from_html(html: str) -> str:
    """Extract readable discussion content from HTML."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    blocks: list[str] = []

    for selector in [
        "article",
        "main",
        "div",
        "section",
        ".post",
        ".comment",
        ".body",
        ".md",
        ".text",
        "p",
    ]:
        for node in soup.select(selector)[:25]:
            text = clean_text(node.get_text(" ", strip=True))
            if len(text) >= 60 and text not in blocks:
                blocks.append(text)

    if not blocks:
        full_text = clean_text(soup.get_text(" ", strip=True))
        if full_text:
            blocks.append(full_text)

    return "\n\n".join(blocks[:12])


def scrape_unofficial_sources(urls: Iterable[str]) -> list[dict]:
    """Scrape unofficial public discussion pages into a standard source structure."""
    scraped: list[dict] = []

    for url in urls:
        if not url or not str(url).strip():
            continue

        normalized_url = str(url).strip()

        try:
            html = fetch_page(normalized_url)
            soup = BeautifulSoup(html, "html.parser")
            title = clean_text(soup.title.get_text(" ", strip=True)) if soup.title else "Unofficial discussion"
            content = extract_content_from_html(html)

            if not content:
                content = "The page loaded, but no readable discussion content was detected in this unofficial source."

            scraped.append(
                {
                    "title": title,
                    "url": normalized_url,
                    "content": content,
                    "source_type": source_label(normalized_url),
                }
            )
        except Exception as exc:  # pragma: no cover - network errors are handled at runtime
            scraped.append(
                {
                    "title": "Unavailable unofficial source",
                    "url": normalized_url,
                    "content": (
                        "This unofficial source could not be accessed automatically. "
                        f"Please confirm the page is public and accessible. Error: {exc}"
                    ),
                    "source_type": source_label(normalized_url),
                }
            )

    return scraped
