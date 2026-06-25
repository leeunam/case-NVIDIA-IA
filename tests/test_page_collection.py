from datetime import UTC, datetime

import pytest

from nvidia_startup_intel.page_collection import (
    FetchResponse,
    _ReadableHTMLParser,
    collect_public_pages,
)


FIXED_TIME = datetime(2026, 6, 14, 12, 0, tzinfo=UTC)


def fixed_clock() -> datetime:
    return FIXED_TIME


def make_fetcher(pages: dict[str, FetchResponse], errors: dict[str, Exception] | None = None):
    errors = errors or {}

    def fetch(url: str) -> FetchResponse:
        if url in errors:
            raise errors[url]
        return pages[url]

    return fetch


def test_collect_simple_html_page_and_relevant_links() -> None:
    pages = {
        "https://startup.ai": FetchResponse(
            url="https://startup.ai/",
            status_code=200,
            body="""
            <html>
              <head><title>Startup AI</title></head>
              <body>
                <nav>Menu</nav>
                <main>Plataforma de IA para analise de documentos.</main>
                <a href="/sobre">Sobre</a>
                <a href="/produtos">Produtos</a>
                <a href="/assets/logo.png">Logo</a>
                <a href="https://external.example/news">Externo</a>
              </body>
            </html>
            """,
        ),
        "https://startup.ai/sobre": FetchResponse(
            url="https://startup.ai/sobre",
            status_code=200,
            body="<html><head><title>Sobre</title></head><body>Time brasileiro de IA.</body></html>",
        ),
        "https://startup.ai/produtos": FetchResponse(
            url="https://startup.ai/produtos",
            status_code=200,
            body="<html><head><title>Produtos</title></head><body>Produto de automacao com IA.</body></html>",
        ),
    }

    result = collect_public_pages(
        "https://startup.ai/",
        fetcher=make_fetcher(pages),
        max_pages=3,
        max_depth=1,
        clock=fixed_clock,
    )

    assert result.errors == ()
    assert [page.url for page in result.pages] == [
        "https://startup.ai",
        "https://startup.ai/produtos",
        "https://startup.ai/sobre",
    ]
    assert result.pages[0].title == "Startup AI"
    assert "Plataforma de IA" in result.pages[0].main_text
    assert result.pages[0].collected_at == "2026-06-14T12:00:00+00:00"
    assert result.pages[0].status_code == 200


def test_collect_page_with_missing_content_as_unknown() -> None:
    pages = {
        "https://empty.ai": FetchResponse(
            url="https://empty.ai/",
            status_code=200,
            body="<html><head></head><body><script>ignored()</script></body></html>",
        )
    }

    result = collect_public_pages(
        "https://empty.ai/",
        fetcher=make_fetcher(pages),
        clock=fixed_clock,
    )

    assert len(result.pages) == 1
    assert result.pages[0].title == "unknown"
    assert result.pages[0].main_text == "unknown"


def test_html_parser_closes_most_recent_matching_tag() -> None:
    parser = _ReadableHTMLParser()

    parser.handle_starttag("div", [])
    parser.handle_starttag("section", [])
    parser.handle_starttag("div", [])
    parser.handle_endtag("div")

    assert parser._tag_stack == ["div", "section"]


def test_records_fetch_failure_without_stopping_collection() -> None:
    pages = {
        "https://startup.ai": FetchResponse(
            url="https://startup.ai/",
            status_code=200,
            body="""
            <html>
              <head><title>Startup AI</title></head>
              <body>
                Home
                <a href="/sobre">Sobre</a>
                <a href="/blog">Blog</a>
              </body>
            </html>
            """,
        ),
        "https://startup.ai/blog": FetchResponse(
            url="https://startup.ai/blog",
            status_code=200,
            body="<html><head><title>Blog</title></head><body>Noticias de IA.</body></html>",
        ),
    }
    errors = {"https://startup.ai/sobre": TimeoutError("timeout")}

    result = collect_public_pages(
        "https://startup.ai/",
        fetcher=make_fetcher(pages, errors),
        max_pages=3,
        max_depth=1,
        clock=fixed_clock,
    )

    assert [page.url for page in result.pages] == [
        "https://startup.ai",
        "https://startup.ai/blog",
    ]
    assert len(result.errors) == 1
    assert result.errors[0].url == "https://startup.ai/sobre"
    assert result.errors[0].error_type == "TimeoutError"
    assert result.errors[0].message == "timeout"


def test_avoids_repeated_urls_and_respects_max_pages() -> None:
    pages = {
        "https://startup.ai": FetchResponse(
            url="https://startup.ai/",
            status_code=200,
            body="""
            <html>
              <head><title>Startup AI</title></head>
              <body>
                Home
                <a href="/sobre">Sobre</a>
                <a href="/sobre/">Sobre duplicado</a>
                <a href="/sobre#time">Sobre fragmento</a>
                <a href="/carreiras">Carreiras</a>
              </body>
            </html>
            """,
        ),
        "https://startup.ai/sobre": FetchResponse(
            url="https://startup.ai/sobre",
            status_code=200,
            body="<html><head><title>Sobre</title></head><body>Sobre a empresa.</body></html>",
        ),
        "https://startup.ai/carreiras": FetchResponse(
            url="https://startup.ai/carreiras",
            status_code=200,
            body="<html><head><title>Carreiras</title></head><body>Vagas.</body></html>",
        ),
    }

    result = collect_public_pages(
        "https://startup.ai/",
        fetcher=make_fetcher(pages),
        max_pages=2,
        max_depth=1,
        clock=fixed_clock,
    )

    assert [page.url for page in result.pages] == [
        "https://startup.ai",
        "https://startup.ai/carreiras",
    ]


def test_respects_max_depth() -> None:
    pages = {
        "https://startup.ai": FetchResponse(
            url="https://startup.ai/",
            status_code=200,
            body="<html><body>Home <a href='/blog'>Blog</a></body></html>",
        ),
        "https://startup.ai/blog": FetchResponse(
            url="https://startup.ai/blog",
            status_code=200,
            body="<html><body>Blog <a href='/blog/post-ia'>Post</a></body></html>",
        ),
        "https://startup.ai/blog/post-ia": FetchResponse(
            url="https://startup.ai/blog/post-ia",
            status_code=200,
            body="<html><body>Post sobre IA.</body></html>",
        ),
    }

    result = collect_public_pages(
        "https://startup.ai/",
        fetcher=make_fetcher(pages),
        max_pages=5,
        max_depth=1,
        clock=fixed_clock,
    )

    assert [page.url for page in result.pages] == [
        "https://startup.ai",
        "https://startup.ai/blog",
    ]


def test_max_pages_must_be_positive() -> None:
    with pytest.raises(ValueError, match="max_pages must be greater than zero"):
        collect_public_pages("https://startup.ai/", max_pages=0)
