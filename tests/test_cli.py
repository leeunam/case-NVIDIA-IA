from __future__ import annotations

from datetime import UTC, datetime
from io import StringIO
import json

from nvidia_startup_intel.cli import main
from nvidia_startup_intel.page_collection import FetchResponse


FIXED_TIME = datetime(2026, 6, 26, 9, 30, tzinfo=UTC)


def fixed_clock() -> datetime:
    return FIXED_TIME


def test_collect_pages_cli_outputs_controlled_collection_json() -> None:
    stdout = StringIO()
    pages = {
        "https://startup.ai": FetchResponse(
            url="https://startup.ai/",
            status_code=200,
            body=(
                "<html><head><title>Startup AI</title></head>"
                "<body>Resumo: Plataforma AI-native brasileira.</body></html>"
            ),
        )
    }

    exit_code = main(
        [
            "collect-pages",
            "https://startup.ai/",
            "--max-pages",
            "1",
            "--max-depth",
            "0",
        ],
        stdout=stdout,
        fetcher=_fetcher(pages),
        playwright_renderer=_fetcher(pages),
        robots_fetcher=_allow_robots,
        clock=fixed_clock,
    )

    payload = json.loads(stdout.getvalue())

    assert exit_code == 0
    assert payload["schema_version"] == "collection_cli_result.v1"
    assert payload["run_id"] == "cli-20260626T093000Z"
    assert payload["input_url"] == "https://startup.ai/"
    assert payload["options"]["max_pages"] == 1
    assert payload["options"]["max_depth"] == 0
    assert payload["options"]["render_js"] is True
    assert payload["options"]["robots_policy"] == "conservative"
    assert payload["pages"][0]["url"] == "https://startup.ai"
    assert payload["pages"][0]["title"] == "Startup AI"
    assert "AI-native" in payload["pages"][0]["main_text"]
    assert payload["errors"] == []


def test_collect_pages_cli_can_render_javascript_with_injected_playwright_boundary() -> None:
    stdout = StringIO()

    exit_code = main(
        [
            "collect-pages",
            "https://startup.ai/",
            "--max-pages",
            "1",
        ],
        stdout=stdout,
        fetcher=_fetcher(
            {
                "https://startup.ai": FetchResponse(
                    url="https://startup.ai/",
                    status_code=200,
                    body="<html><body><div id='root'></div><script>render()</script></body></html>",
                )
            }
        ),
        playwright_renderer=_fetcher(
            {
                "https://startup.ai": FetchResponse(
                    url="https://startup.ai/",
                    status_code=200,
                    body=(
                        "<html><head><title>Startup AI Rendered</title></head>"
                        "<body>Conteudo renderizado com IA em producao.</body></html>"
                    ),
                )
            }
        ),
        robots_fetcher=_allow_robots,
        clock=fixed_clock,
    )

    payload = json.loads(stdout.getvalue())

    assert exit_code == 0
    assert payload["options"]["render_js"] is True
    assert payload["pages"][0]["title"] == "Startup AI Rendered"
    assert "renderizado" in payload["pages"][0]["main_text"]
    assert payload["pages"][0]["extraction_strategy"] == "stdlib_html_parser+playwright"


def test_collect_pages_cli_can_disable_playwright_for_deterministic_debugging() -> None:
    stdout = StringIO()

    exit_code = main(
        [
            "collect-pages",
            "https://startup.ai/",
            "--max-pages",
            "1",
            "--no-render-js",
        ],
        stdout=stdout,
        fetcher=_fetcher(
            {
                "https://startup.ai": FetchResponse(
                    url="https://startup.ai/",
                    status_code=200,
                    body="<html><body><div id='root'></div><script>render()</script></body></html>",
                )
            }
        ),
        playwright_renderer=_fetcher(
            {
                "https://startup.ai": FetchResponse(
                    url="https://startup.ai/",
                    status_code=200,
                    body="<html><body>Conteudo renderizado.</body></html>",
                )
            }
        ),
        robots_fetcher=_allow_robots,
        clock=fixed_clock,
    )

    payload = json.loads(stdout.getvalue())

    assert exit_code == 0
    assert payload["options"]["render_js"] is False
    assert payload["pages"][0]["main_text"] == "unknown"
    assert payload["pages"][0]["needs_js_rendering"] is True


def test_collect_pages_cli_can_write_json_output_file(tmp_path) -> None:
    output_path = tmp_path / "collection.json"
    pages = {
        "https://startup.ai": FetchResponse(
            url="https://startup.ai/",
            status_code=200,
            body="<html><body>Coleta controlada.</body></html>",
        )
    }

    exit_code = main(
        [
            "collect-pages",
            "https://startup.ai/",
            "--max-pages",
            "1",
            "--output",
            str(output_path),
        ],
        fetcher=_fetcher(pages),
        playwright_renderer=_fetcher(pages),
        robots_fetcher=_allow_robots,
        clock=fixed_clock,
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["pages"][0]["main_text"] == "Coleta controlada."


def _fetcher(pages: dict[str, FetchResponse]):
    def fetch(url: str) -> FetchResponse:
        return pages[url]

    return fetch


def _allow_robots(url: str) -> str:
    return "User-agent: *\nAllow: /\n"
