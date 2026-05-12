"""Article retrieval and web search logic for STF tools."""

from __future__ import annotations

import logging
import os

import requests
from bs4 import BeautifulSoup
from openai import OpenAI

from tools.schemas import ArticleContext, FetchArticleContentInput, WebSearchInput, WebSearchOutput
from utils.stf_tool_utils import absolute_url, is_relevant_article_image, normalize_html_text


logger = logging.getLogger(__name__)


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


def web_search_logic(params: WebSearchInput) -> WebSearchOutput:
    """Search the web for article content or supporting source material."""

    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.responses.create(
            model=os.getenv("STF_WEB_SEARCH_MODEL", "gpt-5-mini"),
            tools=[{"type": "web_search_preview"}],
            input=(
                "Find source-grounded content for this sequence-function research request. "
                "Return concise article text, key facts, and source URLs when available.\n\n"
                f"Query: {params.query}"
            ),
        )
        content = response.output_text or ""
        return WebSearchOutput(success=bool(content), query=params.query, content=content)
    except Exception as exc:
        logger.error("web_search failed for %s: %s", params.query, exc, exc_info=True)
        return WebSearchOutput(success=False, query=params.query, content="", error=str(exc))
