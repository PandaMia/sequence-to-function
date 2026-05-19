"""Article retrieval and web search logic for STF tools."""

from __future__ import annotations

import logging
import os
import json
import re
from typing import Any
from urllib.parse import urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from openai import OpenAI

from tools.schemas import (
    ArticleContext,
    FetchArticleContentInput,
    LiteratureCandidate,
    LiteratureSearchInput,
    LiteratureSearchOutput,
    WebSearchInput,
    WebSearchOutput,
)
from utils.app_context import get_app_state_context, get_session_id_context
from utils.secret_manager import get_openai_api_key
from utils.stf_tool_utils import absolute_url, is_relevant_article_image, normalize_html_text
from utils.usage_limits import UsageLimitExceeded


logger = logging.getLogger(__name__)


async def _check_web_search_limit() -> None:
    app_state = get_app_state_context()
    session_id = get_session_id_context()
    if app_state is not None and session_id:
        await app_state.usage_limiter.check_web_search(session_id)


def _build_literature_query(params: LiteratureSearchInput) -> str:
    identifiers = [params.gene.strip()]
    if params.protein_uniprot_id:
        identifiers.append(params.protein_uniprot_id.strip())
    topic = params.query.strip() if params.query else "sequence function mutations domains longevity aging"
    return " ".join(part for part in [*identifiers, topic] if part)


def _loads_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            parsed = json.loads(text[start : end + 1])
            return parsed if isinstance(parsed, dict) else {}
        raise


def _normalize_source_url(url: str) -> str:
    parsed = urlparse(url.strip())
    normalized = parsed._replace(fragment="")
    path = normalized.path.rstrip("/") or normalized.path
    normalized = normalized._replace(path=path)
    return urlunparse(normalized)


def _fallback_candidates_from_text(raw: str, max_results: int) -> list[LiteratureCandidate]:
    urls = re.findall(r"https?://[^\s\]\)\}\>\"']+", raw)
    candidates = []
    for url in urls:
        clean_url = _normalize_source_url(url.rstrip(".,;"))
        candidates.append(
            LiteratureCandidate(
                title="",
                url=clean_url,
                snippet="Candidate source URL extracted from web search output.",
                source_type="other",
                relevance_score=0.5,
            )
        )
    return _deduplicate_candidates(candidates, max_results)


def _candidate_from_mapping(item: dict[str, Any]) -> LiteratureCandidate | None:
    url = str(item.get("url") or "").strip()
    if not url:
        return None

    source_type = str(item.get("source_type") or "other")
    if source_type not in {"research_article", "review", "database_page", "other"}:
        source_type = "other"

    try:
        relevance_score = float(item.get("relevance_score", 1.0))
    except (TypeError, ValueError):
        relevance_score = 1.0
    relevance_score = min(max(relevance_score, 0.0), 1.0)

    return LiteratureCandidate(
        title=str(item.get("title") or ""),
        url=url,
        snippet=str(item.get("snippet") or ""),
        source_type=source_type,
        relevance_score=relevance_score,
    )


def _deduplicate_candidates(candidates: list[LiteratureCandidate], max_results: int) -> list[LiteratureCandidate]:
    unique: list[LiteratureCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        clean_url = _normalize_source_url(candidate.url)
        if not clean_url or clean_url in seen:
            continue
        seen.add(clean_url)
        unique.append(candidate.model_copy(update={"url": clean_url}))
        if len(unique) >= max_results:
            break
    return unique


def fetch_article_content_logic(params: FetchArticleContentInput) -> ArticleContext:
    """Fetch and extract content, relevant images, and PDFs from a research article URL."""

    url = params.url
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        if "unsupported_browser" in response.url or response.status_code == 400:
            alternative_headers = headers.copy()
            alternative_headers["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0"
            )
            response = requests.get(url, headers=alternative_headers, timeout=30, allow_redirects=True)

        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        for element in soup(["script", "style"]):
            element.decompose()

        content = None
        for selector in ("article", ".article-body", ".content", ".main-content", "#content", ".abstract", ".full-text"):
            elements = soup.select(selector)
            if elements:
                content = elements[0]
                break
        if not content:
            content = soup.body or soup

        image_urls: list[str] = []
        for image in soup.find_all("img"):
            src = image.get("src") or image.get("data-src")
            candidate_url = absolute_url(url, src)
            if candidate_url and is_relevant_article_image(image, candidate_url):
                image_urls.append(candidate_url)
        image_urls = list(dict.fromkeys(image_urls))[:8]

        pdf_urls: list[str] = []
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            if href and href.lower().endswith(".pdf"):
                candidate_url = absolute_url(url, href)
                if candidate_url:
                    pdf_urls.append(candidate_url)
        pdf_urls = list(dict.fromkeys(pdf_urls))

        return ArticleContext(
            article_url=url,
            text=normalize_html_text(content),
            image_urls=image_urls,
            pdf_urls=pdf_urls,
        )
    except Exception as exc:
        logger.error("Error fetching article content from %s: %s", url, exc, exc_info=True)
        return ArticleContext(article_url=url, text=None, image_urls=[], pdf_urls=[], error=str(exc))


async def web_search_logic(params: WebSearchInput) -> WebSearchOutput:
    """Search the web for article content or supporting source material."""

    try:
        await _check_web_search_limit()

        client = OpenAI(api_key=get_openai_api_key())
        response = client.responses.create(
            model=os.getenv("STF_WEB_SEARCH_MODEL", "gpt-5.4-nano"),
            tools=[{"type": "web_search_preview"}],
            input=(
                "Find source-grounded content for this sequence-function research request. "
                "Return concise article text, key facts, and source URLs when available.\n\n"
                f"Query: {params.query}"
            ),
        )
        content = response.output_text or ""
        return WebSearchOutput(success=bool(content), query=params.query, content=content)
    except UsageLimitExceeded as exc:
        logger.warning("web_search limit exceeded for %s: %s", params.query, exc.message)
        return WebSearchOutput(success=False, query=params.query, content="", error=exc.message)
    except Exception as exc:
        logger.error("web_search failed for %s: %s", params.query, exc, exc_info=True)
        return WebSearchOutput(success=False, query=params.query, content="", error=str(exc))


async def search_literature_logic(params: LiteratureSearchInput) -> LiteratureSearchOutput:
    """Find candidate public sources for gene-level sequence-function evidence."""

    query = _build_literature_query(params)
    try:
        await _check_web_search_limit()

        client = OpenAI(api_key=get_openai_api_key())
        response = client.responses.create(
            model=os.getenv("STF_WEB_SEARCH_MODEL", "gpt-5.4-nano"),
            tools=[{"type": "web_search_preview"}],
            input=(
                "Find public source URLs for sequence-to-function evidence about a gene or protein. "
                "Prioritize PubMed, PubMed Central, DOI landing pages, journal publisher pages, UniProt, "
                "InterPro, GenAge, Open Genes, and other reputable biological databases. Prefer sources "
                "that discuss protein domains, sequence intervals, mutations, variants, orthologs, "
                "functional outcomes, reprogramming, aging, lifespan, or longevity. "
                "Return ONLY a JSON object with this schema: "
                '{"results":[{"title":"string","url":"string","snippet":"string",'
                '"source_type":"research_article|review|database_page|other","relevance_score":0.0}]}. '
                "Do not include duplicate URLs.\n\n"
                f"Gene: {params.gene}\n"
                f"UniProt ID: {params.protein_uniprot_id or ''}\n"
                f"Extra topic: {params.query or ''}\n"
                f"Maximum results: {params.max_results}\n"
                f"Search query: {query}"
            ),
        )
        raw = response.output_text or ""
        try:
            parsed = _loads_json_object(raw)
            raw_results = parsed.get("results", [])
            candidates = []
            for item in raw_results:
                if not isinstance(item, dict):
                    continue
                candidate = _candidate_from_mapping(item)
                if candidate:
                    candidates.append(candidate)
            candidates = _deduplicate_candidates(candidates, params.max_results)
        except Exception:
            logger.warning("search_literature returned non-JSON output for %s", query, exc_info=True)
            candidates = _fallback_candidates_from_text(raw, params.max_results)

        return LiteratureSearchOutput(
            success=bool(candidates),
            query=query,
            results=candidates,
            result_count=len(candidates),
            error=None if candidates else "No candidate source URLs found.",
        )
    except UsageLimitExceeded as exc:
        logger.warning("search_literature limit exceeded for %s: %s", query, exc.message)
        return LiteratureSearchOutput(success=False, query=query, results=[], result_count=0, error=exc.message)
    except Exception as exc:
        logger.error("search_literature failed for %s: %s", query, exc, exc_info=True)
        return LiteratureSearchOutput(success=False, query=query, results=[], result_count=0, error=str(exc))
