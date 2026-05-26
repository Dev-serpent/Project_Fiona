from __future__ import annotations

import heapq
import re
import time
import urllib.parse
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


DUCKDUCKGO_HTML_URL = "https://duckduckgo.com/html/"
DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0"}


@dataclass(frozen=True)
class MinedPage:
    topic: str
    url: str
    title: str
    summary: str
    depth: int = 0
    parent_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def decode_duckduckgo_href(href: str) -> str:
    parsed = urllib.parse.urlparse(href)
    query = urllib.parse.parse_qs(parsed.query)
    if "uddg" in query and query["uddg"]:
        return query["uddg"][0]
    return href


def parse_search_results(html: str, *, max_results: int) -> list[str]:
    parser = _DataClientHTMLParser()
    parser.feed(html)
    return _dedupe(decode_duckduckgo_href(href) for href in parser.search_result_links)[:max_results]


def web_search(
    topic: str,
    *,
    max_results: int = 50,
    sleep_seconds: float = 1.0,
    fetch: Callable[..., Any] | None = None,
) -> list[str]:
    if max_results < 1:
        return []
    fetcher = fetch or _requests_module().get
    results: list[str] = []
    page = 0
    while len(results) < max_results:
        response = fetcher(
            DUCKDUCKGO_HTML_URL,
            params={"q": topic, "s": str(page * 50)},
            headers=DEFAULT_HEADERS,
            timeout=10,
        )
        html = getattr(response, "text", "")
        found = parse_search_results(str(html), max_results=max_results - len(results))
        if not found:
            break
        results.extend(found)
        results = _dedupe(results)
        page += 1
        if len(results) < max_results and sleep_seconds > 0:
            time.sleep(sleep_seconds)
    return results[:max_results]


def extract_page_text(html: str) -> tuple[str, str]:
    parser = _DataClientHTMLParser()
    parser.feed(html)
    title = re.sub(r"\s+", " ", parser.title).strip() or "No Title"
    text = " ".join(re.sub(r"\s+", " ", paragraph).strip() for paragraph in parser.paragraphs if paragraph.strip())
    return title, text


def extract_links(html: str, base_url: str) -> list[str]:
    parser = _DataClientHTMLParser()
    parser.feed(html)
    links: list[str] = []
    for href in parser.links:
        normalized = normalize_url(href, base_url=base_url)
        if normalized:
            links.append(normalized)
    return _dedupe(links)


def normalize_url(href: str, *, base_url: str = "") -> str:
    href = href.strip()
    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return ""
    absolute = urllib.parse.urljoin(base_url, href)
    parsed = urllib.parse.urlparse(absolute)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    cleaned = parsed._replace(fragment="")
    return urllib.parse.urlunparse(cleaned)


def same_domain(url: str, other_url: str) -> bool:
    return urllib.parse.urlparse(url).netloc.lower() == urllib.parse.urlparse(other_url).netloc.lower()


def scrape_page(url: str, *, fetch: Callable[..., Any] | None = None) -> tuple[str | None, str]:
    fetcher = fetch or _requests_module().get
    try:
        response = fetcher(url, headers=DEFAULT_HEADERS, timeout=10)
    except Exception:
        return None, ""
    return extract_page_text(str(getattr(response, "text", "")))


def fetch_page_html(url: str, *, fetch: Callable[..., Any] | None = None) -> str:
    fetcher = fetch or _requests_module().get
    try:
        response = fetcher(url, headers=DEFAULT_HEADERS, timeout=10)
    except Exception:
        return ""
    return str(getattr(response, "text", ""))


def summarize(text: str, *, max_sentences: int = 5) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return ""
    sentences = re.split(r"(?<=[.!?]) +", cleaned)
    if len(sentences) <= max_sentences:
        return cleaned

    frequencies: dict[str, float] = {}
    for word in re.findall(r"\w+", cleaned.lower()):
        frequencies[word] = frequencies.get(word, 0.0) + 1.0
    max_frequency = max(frequencies.values(), default=1.0)
    for word in frequencies:
        frequencies[word] /= max_frequency

    scores: dict[str, float] = {}
    for sentence in sentences:
        for word in re.findall(r"\w+", sentence.lower()):
            if word in frequencies:
                scores[sentence] = scores.get(sentence, 0.0) + frequencies[word]

    best = heapq.nlargest(max_sentences, scores, key=scores.get)
    return " ".join(best)


def mine_topic(
    topic: str,
    save_path: Path,
    *,
    max_links: int = 30,
    max_sentences: int = 5,
    sleep_seconds: float = 0.5,
    search_fetch: Callable[..., Any] | None = None,
    page_fetch: Callable[..., Any] | None = None,
    log: Callable[[str], None] | None = None,
) -> list[MinedPage]:
    logger = log or (lambda _message: None)
    logger(f"Searching for {topic!r}")
    links = web_search(topic, max_results=max_links, sleep_seconds=sleep_seconds, fetch=search_fetch)
    logger(f"Found {len(links)} links")

    pages: list[MinedPage] = []
    for index, url in enumerate(links, start=1):
        logger(f"[{index}/{len(links)}] Scraping {url}")
        title, text = scrape_page(url, fetch=page_fetch)
        if text:
            pages.append(
                MinedPage(
                    topic=topic,
                    url=url,
                    title=title or "No Title",
                    summary=summarize(text, max_sentences=max_sentences),
                )
            )
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    _write_csv(save_path, pages)
    logger(f"Saved {len(pages)} pages into {save_path}")
    return pages


def deep_research_topic(
    topic: str,
    save_path: Path,
    *,
    seed_links: int = 10,
    page_limit: int = 50,
    max_depth: int = 1,
    max_sentences: int = 5,
    same_domain_only: bool = True,
    sleep_seconds: float = 0.5,
    search_fetch: Callable[..., Any] | None = None,
    page_fetch: Callable[..., Any] | None = None,
    log: Callable[[str], None] | None = None,
) -> list[MinedPage]:
    logger = log or (lambda _message: None)
    logger(f"Deep research for {topic!r}")
    seeds = web_search(topic, max_results=seed_links, sleep_seconds=sleep_seconds, fetch=search_fetch)
    logger(f"Found {len(seeds)} seed links")

    queue: list[tuple[str, int, str]] = [(url, 0, "") for url in seeds]
    visited: set[str] = set()
    pages: list[MinedPage] = []

    while queue and len(visited) < page_limit:
        url, depth, parent_url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        logger(f"[{len(visited)}/{page_limit}] depth={depth} {url}")

        html = fetch_page_html(url, fetch=page_fetch)
        if not html:
            continue
        title, text = extract_page_text(html)
        if text:
            pages.append(
                MinedPage(
                    topic=topic,
                    url=url,
                    title=title,
                    summary=summarize(text, max_sentences=max_sentences),
                    depth=depth,
                    parent_url=parent_url,
                )
            )

        if depth >= max_depth:
            continue
        for child_url in extract_links(html, url):
            if child_url in visited:
                continue
            if same_domain_only and not same_domain(url, child_url):
                continue
            queue.append((child_url, depth + 1, url))

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    _write_csv(save_path, pages)
    logger(f"Saved {len(pages)} pages into {save_path}")
    return pages


def _write_csv(path: Path, pages: Iterable[MinedPage]) -> None:
    pandas = _pandas_module()
    path.parent.mkdir(parents=True, exist_ok=True)
    pandas.DataFrame([page.to_dict() for page in pages]).to_csv(path, index=False)


def _dedupe(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _requests_module() -> Any:
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("DataClient requires the 'requests' package. Install Fiona with project dependencies.") from exc
    return requests


def _pandas_module() -> Any:
    try:
        import pandas
    except ImportError as exc:
        raise RuntimeError("DataClient requires the 'pandas' package. Install Fiona with project dependencies.") from exc
    return pandas


class _DataClientHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.paragraphs: list[str] = []
        self.links: list[str] = []
        self.search_result_links: list[str] = []
        self._in_title = False
        self._paragraph_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "title":
            self._in_title = True
        if tag.lower() == "p":
            self._paragraph_parts = []
        if tag.lower() == "a":
            href = attributes.get("href", "")
            if href:
                self.links.append(href)
                classes = set(attributes.get("class", "").split())
                if "result__a" in classes:
                    self.search_result_links.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False
        if tag.lower() == "p" and self._paragraph_parts is not None:
            self.paragraphs.append(" ".join(self._paragraph_parts))
            self._paragraph_parts = None

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if self._paragraph_parts is not None:
            self._paragraph_parts.append(data)
