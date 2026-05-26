"""Data collection and lightweight research tools for Fiona."""

from __future__ import annotations

from DataClient.miner import (
    MinedPage,
    deep_research_topic,
    decode_duckduckgo_href,
    extract_links,
    extract_page_text,
    mine_topic,
    normalize_url,
    parse_search_results,
    scrape_page,
    summarize,
    web_search,
)

__all__ = [
    "MinedPage",
    "deep_research_topic",
    "decode_duckduckgo_href",
    "extract_links",
    "extract_page_text",
    "mine_topic",
    "normalize_url",
    "parse_search_results",
    "scrape_page",
    "summarize",
    "web_search",
]
