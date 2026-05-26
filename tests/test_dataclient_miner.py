from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from DataClient.miner import (
    decode_duckduckgo_href,
    deep_research_topic,
    extract_links,
    extract_page_text,
    mine_topic,
    normalize_url,
    parse_search_results,
    summarize,
)


class FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class DataClientMinerTests(unittest.TestCase):
    def test_decodes_duckduckgo_redirect_href(self) -> None:
        href = "/l/?uddg=https%3A%2F%2Fexample.com%2Fdocs&rut=abc"

        self.assertEqual(decode_duckduckgo_href(href), "https://example.com/docs")

    def test_parses_and_dedupes_search_results(self) -> None:
        html = """
        <a class="result__a" href="/l/?uddg=https%3A%2F%2Fexample.com%2Fa">A</a>
        <a class="result__a" href="https://example.com/b">B</a>
        <a class="result__a" href="https://example.com/b">B</a>
        """

        self.assertEqual(parse_search_results(html, max_results=10), ["https://example.com/a", "https://example.com/b"])

    def test_extracts_page_title_and_paragraph_text(self) -> None:
        title, text = extract_page_text("<html><title>Page</title><p>First paragraph.</p><p>Second paragraph.</p></html>")

        self.assertEqual(title, "Page")
        self.assertEqual(text, "First paragraph. Second paragraph.")

    def test_normalizes_and_extracts_page_links(self) -> None:
        html = """
        <a href="/docs">Docs</a>
        <a href="https://other.example/page#section">Other</a>
        <a href="mailto:test@example.com">Mail</a>
        """

        self.assertEqual(normalize_url("/docs", base_url="https://example.com/start"), "https://example.com/docs")
        self.assertEqual(
            extract_links(html, "https://example.com/start"),
            ["https://example.com/docs", "https://other.example/page"],
        )

    def test_summarize_returns_top_sentences(self) -> None:
        text = "Alpha topic matters. Beta is small. Alpha appears again. Alpha topic wins."

        summary = summarize(text, max_sentences=2)

        self.assertIn("Alpha", summary)
        self.assertLessEqual(len(summary.split(".")), 3)

    def test_mine_topic_writes_csv_without_network(self) -> None:
        search_html = """
        <a class="result__a" href="https://example.com/a">A</a>
        <a class="result__a" href="https://example.com/b">B</a>
        """
        pages = {
            "https://example.com/a": "<html><title>A</title><p>Alpha page. Alpha useful data.</p></html>",
            "https://example.com/b": "<html><title>B</title><p>Beta page. Beta useful data.</p></html>",
        }

        def search_fetch(*_args: object, **_kwargs: object) -> FakeResponse:
            return FakeResponse(search_html)

        def page_fetch(url: str, *_args: object, **_kwargs: object) -> FakeResponse:
            return FakeResponse(pages[url])

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "results.csv"
            mined = mine_topic(
                "alpha",
                output,
                max_links=2,
                sleep_seconds=0,
                search_fetch=search_fetch,
                page_fetch=page_fetch,
            )

            self.assertEqual(len(mined), 2)
            csv_text = output.read_text(encoding="utf-8")

        self.assertIn("https://example.com/a", csv_text)
        self.assertIn("Alpha useful data", csv_text)

    def test_deep_research_follows_same_domain_links(self) -> None:
        search_html = '<a class="result__a" href="https://example.com/root">Root</a>'
        pages = {
            "https://example.com/root": """
                <html><title>Root</title><p>Root research page.</p>
                <a href="/child">Child</a>
                <a href="https://external.example/skip">External</a></html>
            """,
            "https://example.com/child": "<html><title>Child</title><p>Child research page.</p></html>",
        }

        def search_fetch(*_args: object, **_kwargs: object) -> FakeResponse:
            return FakeResponse(search_html)

        def page_fetch(url: str, *_args: object, **_kwargs: object) -> FakeResponse:
            return FakeResponse(pages[url])

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "deep.csv"
            mined = deep_research_topic(
                "research",
                output,
                seed_links=1,
                page_limit=5,
                max_depth=1,
                sleep_seconds=0,
                search_fetch=search_fetch,
                page_fetch=page_fetch,
            )
            csv_text = output.read_text(encoding="utf-8")

        self.assertEqual([page.url for page in mined], ["https://example.com/root", "https://example.com/child"])
        self.assertIn("https://example.com/root", csv_text)
        self.assertIn("https://example.com/child", csv_text)
        self.assertNotIn("external.example", csv_text)


if __name__ == "__main__":
    unittest.main()
