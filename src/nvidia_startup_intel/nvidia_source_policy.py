"""Official NVIDIA source policy shared by Knowledge, Recommendation, and Briefing."""

from __future__ import annotations

from urllib.parse import urlparse


SUPPORTED_NVIDIA_SOURCE_TYPES = frozenset(
    {
        "official_nvidia_developer_page",
        "official_nvidia_documentation",
        "official_nvidia_product_page",
        "official_nvidia_program_page",
        "official_nvidia_industry_page",
        "official_nvidia_code_repository",
        "official_nvidia_project_page",
        "official_nvidia_blog",
        "official_nvidia_video",
    }
)

OFFICIAL_NVIDIA_VIDEO_URLS = frozenset(
    {
        "https://youtube.com/playlist?list=PLBaUJRFQ-j_WJZdZfFNsgUWDWF1Ldjp_X",
        "https://youtu.be/NmZDQSdUVUQ",
        "https://www.youtube.com/live/fWfkE6cibwQ",
    }
)


def is_official_nvidia_source_url(source_url: str) -> bool:
    """Return whether a source URL is accepted as official NVIDIA evidence."""

    parsed_url = urlparse(source_url)
    host = parsed_url.hostname or ""
    if host == "nvidia.com" or host.endswith(".nvidia.com"):
        return True
    if host == "github.com":
        return parsed_url.path.startswith("/NVIDIA/")
    if host == "rapids.ai" or host.endswith(".rapids.ai"):
        return True
    return source_url in OFFICIAL_NVIDIA_VIDEO_URLS
