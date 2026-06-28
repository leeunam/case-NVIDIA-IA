from __future__ import annotations

from datetime import UTC, datetime
from io import StringIO
import json

from nvidia_startup_intel.page_collection import FetchResponse, extract_readable_html
from nvidia_startup_intel.production_scraping_smoke import main, run_production_scraping_smoke
from nvidia_startup_intel.scraping_policy import ScrapingPolicy


FIXED_TIME = datetime(2026, 6, 27, 14, 15, tzinfo=UTC)


def test_production_scraping_smoke_reports_quality_for_configurable_startup_urls() -> None:
    result = run_production_scraping_smoke(
        ("https://startup.ai/",),
        startup_names={"https://startup.ai/": "Startup AI"},
        fetcher=_fetcher(),
        playwright_renderer=_fetcher(),
        html_extractor=extract_readable_html,
        robots_fetcher=_allow_robots,
        clock=lambda: FIXED_TIME,
        timer=_Timer(10.0, 10.42),
        max_pages=1,
        max_depth=0,
    )

    payload = result.to_dict()
    startup_report = payload["startup_reports"][0]

    assert payload["schema_version"] == "production_scraping_validation.v1"
    assert payload["run_id"] == "production-scraping-20260627T141500Z"
    assert startup_report["input_url"] == "https://startup.ai/"
    assert startup_report["startup_name"] == "Startup AI"
    assert startup_report["collection_strategy"] == "playwright_first"
    assert startup_report["robots_decision"]["allowed"] is True
    assert startup_report["robots_decision"]["reason"] == "allowed"
    assert startup_report["crawl_limits"] == {"max_pages": 1, "max_depth": 0}
    assert startup_report["elapsed_ms"] == 420
    assert startup_report["page_count"] == 1
    assert startup_report["error_count"] == 0
    assert startup_report["pages"][0]["extraction_strategy"].endswith("+playwright")
    assert startup_report["pages"][0]["text_length"] > 80
    assert startup_report["empty_or_low_text_pages"] == []
    assert startup_report["profile_quality"]["profile_schema_version"] == "startup_profile.v1"
    assert startup_report["profile_quality"]["completeness_rate"] == 1.0
    assert startup_report["profile_quality"]["unknown_rate"] == 0.0
    assert startup_report["profile_quality"]["conflicts"] == []
    assert startup_report["quality_reasons"] == ["ready_for_ai_native_evaluation"]
    assert startup_report["ready_for_ai_native_assessment"] is True


def test_production_scraping_smoke_main_outputs_json_for_url_list() -> None:
    stdout = StringIO()

    exit_code = main(
        [
            "https://startup.ai/",
            "https://vision.ai/",
            "--max-pages",
            "1",
            "--max-depth",
            "0",
        ],
        stdout=stdout,
        fetcher=_fetcher(),
        playwright_renderer=_fetcher(),
        html_extractor=extract_readable_html,
        robots_fetcher=_allow_robots,
        clock=lambda: FIXED_TIME,
        timer=_Timer(10.0, 10.1, 20.0, 20.2),
    )

    payload = json.loads(stdout.getvalue())

    assert exit_code == 0
    assert payload["schema_version"] == "production_scraping_validation.v1"
    assert [report["input_url"] for report in payload["startup_reports"]] == [
        "https://startup.ai/",
        "https://vision.ai/",
    ]
    assert all(
        report["collection_strategy"] == "playwright_first"
        for report in payload["startup_reports"]
    )


def test_production_scraping_smoke_audits_policy_block_without_fetching_pages() -> None:
    robots_fetches: list[str] = []

    result = run_production_scraping_smoke(
        ("https://startup.ai/",),
        startup_names={"https://startup.ai/": "Startup AI"},
        fetcher=_fail_if_collected,
        playwright_renderer=_fail_if_collected,
        html_extractor=extract_readable_html,
        robots_fetcher=lambda url: robots_fetches.append(url) or _allow_robots(url),
        scraping_policy=ScrapingPolicy(blocked_domains=frozenset({"startup.ai"})),
        clock=lambda: FIXED_TIME,
        timer=_Timer(10.0, 10.01),
        max_pages=1,
        max_depth=0,
    )

    startup_report = result.to_dict()["startup_reports"][0]

    assert robots_fetches == []
    assert startup_report["policy_decision"]["allowed"] is False
    assert startup_report["policy_decision"]["reason"] == "blocked_domain"
    assert startup_report["robots_decision"]["reason"] == "not_checked_policy_blocked"
    assert startup_report["page_count"] == 0
    assert startup_report["error_count"] == 1
    assert startup_report["errors"][0]["error_category"] == "blocked_domain"
    assert startup_report["ready_for_ai_native_assessment"] is False


class _Timer:
    def __init__(self, *values: float) -> None:
        self._values = list(values)

    def __call__(self) -> float:
        return self._values.pop(0)


def _fetcher():
    def fetch(url: str) -> FetchResponse:
        return FetchResponse(
            url=url,
            status_code=200,
            body=(
                "<html><head><title>Startup AI</title></head><body>"
                "Resumo: Plataforma AI-native brasileira para automacao de documentos. "
                "Setor: dados. Produto: Copiloto para operacoes financeiras. "
                "Sinais de IA: modelos proprietarios e fine-tuning. "
                "Tecnologias: inferencia em producao, MLOps e dados proprietarios. "
                "Clientes: bancos. Founders: Ana Silva. Funding: seed. "
                "Localizacao: Sao Paulo, SP."
                "</body></html>"
            ),
        )

    return fetch


def _allow_robots(url: str) -> str:
    return "User-agent: *\nAllow: /\n"


def _fail_if_collected(url: str) -> FetchResponse:
    raise AssertionError(f"URL should not be collected: {url}")
