from datetime import UTC, datetime

import pytest

from nvidia_startup_intel.page_collection import (
    FetchResponse,
    HTMLExtractionResult,
    StaticHTMLExtractionAdapter,
    _ReadableHTMLParser,
    collect_public_pages,
    extract_readable_html,
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


def test_collect_pages_uses_injected_html_extractor_without_changing_output_contract() -> None:
    pages = {
        "https://startup.ai": FetchResponse(
            url="https://startup.ai/",
            status_code=200,
            body="<html><body><div id='root'></div><script>render()</script></body></html>",
        ),
        "https://startup.ai/sobre": FetchResponse(
            url="https://startup.ai/sobre",
            status_code=200,
            body="<html><body>ignored by fixture extractor</body></html>",
        ),
    }

    def fixture_extractor(html: str) -> HTMLExtractionResult:
        if "root" in html:
            return HTMLExtractionResult(
                title="Startup AI",
                main_text="Texto limpo vindo do extrator robusto.",
                links=("/sobre",),
                extraction_strategy="fixture_static_extractor",
                needs_js_rendering=True,
            )
        return extract_readable_html(html)

    result = collect_public_pages(
        "https://startup.ai/",
        fetcher=make_fetcher(pages),
        html_extractor=fixture_extractor,
        max_pages=2,
        max_depth=1,
        clock=fixed_clock,
    )

    assert result.errors == ()
    assert result.pages[0].title == "Startup AI"
    assert result.pages[0].main_text == "Texto limpo vindo do extrator robusto."
    assert result.pages[0].extraction_strategy == "fixture_static_extractor"
    assert result.pages[0].needs_js_rendering is True
    assert [page.url for page in result.pages] == ["https://startup.ai", "https://startup.ai/sobre"]


def test_collect_pages_uses_playwright_renderer_when_static_html_needs_javascript() -> None:
    pages = {
        "https://startup.ai": FetchResponse(
            url="https://startup.ai/",
            status_code=200,
            body="<html><body><div id='root'></div><script>render()</script></body></html>",
        ),
        "https://startup.ai/sobre": FetchResponse(
            url="https://startup.ai/sobre",
            status_code=200,
            body="<html><body>Sobre fallback.</body></html>",
        ),
    }
    rendered_pages = {
        "https://startup.ai": FetchResponse(
            url="https://startup.ai/",
            status_code=200,
            body="""
            <html>
              <head><title>Startup AI Rendered</title></head>
              <body>
                Plataforma AI-native renderizada com evidencias publicas.
                <a href="/sobre">Sobre</a>
              </body>
            </html>
            """,
        ),
        "https://startup.ai/sobre": FetchResponse(
            url="https://startup.ai/sobre",
            status_code=200,
            body="<html><head><title>Sobre Rendered</title></head><body>Sobre renderizado.</body></html>",
        ),
    }

    result = collect_public_pages(
        "https://startup.ai/",
        fetcher=make_fetcher(pages),
        playwright_renderer=make_fetcher(rendered_pages),
        max_pages=2,
        max_depth=1,
        clock=fixed_clock,
    )

    assert result.errors == ()
    assert result.pages[0].title == "Startup AI Rendered"
    assert "AI-native renderizada" in result.pages[0].main_text
    assert result.pages[0].needs_js_rendering is False
    assert result.pages[0].extraction_strategy == "stdlib_html_parser+playwright"
    assert [page.url for page in result.pages] == ["https://startup.ai", "https://startup.ai/sobre"]


def test_collect_pages_uses_playwright_renderer_as_primary_collection_engine_when_configured() -> None:
    pages = {
        "https://startup.ai": FetchResponse(
            url="https://startup.ai/",
            status_code=200,
            body="<html><head><title>Static</title></head><body>Texto estatico.</body></html>",
        )
    }
    rendered_pages = {
        "https://startup.ai": FetchResponse(
            url="https://startup.ai/",
            status_code=200,
            body="<html><head><title>Rendered</title></head><body>Texto do motor Playwright.</body></html>",
        )
    }

    result = collect_public_pages(
        "https://startup.ai/",
        fetcher=make_fetcher(pages),
        playwright_renderer=make_fetcher(rendered_pages),
        max_pages=1,
        clock=fixed_clock,
    )

    assert result.errors == ()
    assert result.pages[0].title == "Rendered"
    assert result.pages[0].main_text == "Texto do motor Playwright."
    assert result.pages[0].extraction_strategy == "stdlib_html_parser+playwright"


def test_collect_pages_records_playwright_failure_without_dropping_static_page() -> None:
    pages = {
        "https://startup.ai": FetchResponse(
            url="https://startup.ai/",
            status_code=200,
            body="<html><body><div id='root'></div><script>render()</script></body></html>",
        )
    }

    def failing_renderer(url: str) -> FetchResponse:
        raise TimeoutError("playwright timeout")

    result = collect_public_pages(
        "https://startup.ai/",
        fetcher=make_fetcher(pages),
        playwright_renderer=failing_renderer,
        max_pages=1,
        clock=fixed_clock,
    )

    assert len(result.pages) == 1
    assert result.pages[0].main_text == "unknown"
    assert result.pages[0].needs_js_rendering is True
    assert len(result.errors) == 1
    assert result.errors[0].url == "https://startup.ai"
    assert result.errors[0].error_type == "TimeoutError"
    assert result.errors[0].message == "playwright timeout"
    assert result.errors[0].error_category == "browser_render_failed"


def test_static_html_extraction_adapter_combines_trafilatura_text_and_beautifulsoup_links() -> None:
    html = """
    <html>
      <head><title>Fallback Title</title></head>
      <body>
        <nav>Menu ruidoso</nav>
        <main>Texto ruidoso de fallback</main>
        <a href="/sobre">Sobre</a>
      </body>
    </html>
    """
    adapter = StaticHTMLExtractionAdapter(
        trafilatura_extract=lambda body: "Texto principal limpo por trafilatura.",
        beautiful_soup_factory=lambda body, parser: _FakeBeautifulSoup(),
    )

    result = adapter(html)

    assert result.title == "Titulo via BeautifulSoup"
    assert result.main_text == "Texto principal limpo por trafilatura."
    assert result.links == ("/sobre-bs", "/produto-bs")
    assert result.extraction_strategy == "trafilatura+beautifulsoup"
    assert result.needs_js_rendering is False


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


class _FakeBeautifulSoup:
    def find(self, tag_name: str) -> "_FakeSoupNode | None":
        if tag_name == "title":
            return _FakeSoupNode(text="Titulo via BeautifulSoup")
        return None

    def find_all(self, tag_name: str) -> list["_FakeSoupNode"]:
        if tag_name == "a":
            return [
                _FakeSoupNode(attrs={"href": "/sobre-bs"}),
                _FakeSoupNode(attrs={"href": "/produto-bs"}),
            ]
        return []

    def get_text(self, separator: str = " ", strip: bool = True) -> str:
        return "Texto fallback via BeautifulSoup"


class _FakeSoupNode:
    def __init__(self, *, text: str = "", attrs: dict[str, str] | None = None) -> None:
        self.text = text
        self.attrs = attrs or {}

    def get_text(self, separator: str = " ", strip: bool = True) -> str:
        return self.text

    def get(self, key: str) -> str | None:
        return self.attrs.get(key)
