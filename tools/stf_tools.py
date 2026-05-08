"""Function tools for the consolidated STF agent."""

from __future__ import annotations

import base64
import json
import logging
import os
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import mygene
import requests
from agents import function_tool
from bs4 import BeautifulSoup
from openai import OpenAI
from sqlalchemy import text

from configs.database import get_db
from tools.schemas import (
    ArticleContext,
    ExecuteSQLQueryInput,
    ExecuteSQLQueryOutput,
    FetchArticleContentInput,
    FindArticleRecordsInput,
    FindArticleRecordsOutput,
    FindGeneRecordsInput,
    FindGeneRecordsOutput,
    GetUniProtIdInput,
    GetUniProtIdOutput,
    SaveSequenceDataInput,
    SaveSequenceDataOutput,
    VisionMediaInput,
    VisionMediaOutput,
    WebSearchInput,
    WebSearchOutput,
)
from tools.tool_wrappers import add_output_schema_to_docstring, flatten_params_from_signature
from utils.database_service import DatabaseService


logger = logging.getLogger(__name__)


def _jsonable(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _row_to_dict(columns: list[str], row: Any) -> dict[str, Any]:
    row_dict: dict[str, Any] = {}
    for index, column in enumerate(columns):
        row_dict[column] = _jsonable(row[index])
    return row_dict


def _download_b64(url: str) -> str:
    """Download an image and convert it to a base64 data URL."""

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    if not content_type.startswith("image/"):
        raise ValueError(f"URL did not return an image (content-type: {content_type})")

    return "data:image/*;base64," + base64.b64encode(response.content).decode("utf-8")


def _download_pdf_b64(url: str) -> tuple[str, str, str]:
    """Download a PDF and return base64 data, content type, and filename."""

    session = requests.Session()

    def is_pdf_bytes(data: bytes) -> bool:
        head = data[:4096].lstrip(b"\xef\xbb\xbf\r\n\t \x00")
        return head.startswith(b"%PDF")

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
    }

    def get(candidate_url: str) -> tuple[requests.Response, str]:
        response = session.get(candidate_url, headers=headers, timeout=60, allow_redirects=True)
        response.raise_for_status()
        return response, (response.headers.get("content-type") or "").lower()

    response, content_type = get(url)
    if content_type.startswith(("application/pdf", "application/octet-stream")) and is_pdf_bytes(response.content):
        filename = url.split("?")[0].split("/")[-1] or "document.pdf"
        return base64.b64encode(response.content).decode("ascii"), "application/pdf", filename

    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query["download"] = ["1"]
    download_url = urlunparse(
        parsed._replace(
            query=urlencode({key: value[0] if len(value) == 1 else value for key, value in query.items()}, doseq=True)
        )
    )

    if download_url != url:
        response, content_type = get(download_url)
        if content_type.startswith(("application/pdf", "application/octet-stream")) and is_pdf_bytes(response.content):
            filename = url.split("?")[0].split("/")[-1] or "document.pdf"
            return base64.b64encode(response.content).decode("ascii"), "application/pdf", filename

    raise ValueError(f"URL did not return a PDF (content-type: {content_type or 'unknown'})")


class STFTools:
    """Function tools available to the single STF agent."""

    @staticmethod
    @function_tool
    @add_output_schema_to_docstring
    @flatten_params_from_signature
    def get_uniprot_id(params: GetUniProtIdInput) -> GetUniProtIdOutput:
        """Resolve a gene symbol to a UniProt Swiss-Prot ID."""

        try:
            mg = mygene.MyGeneInfo()
            result = mg.query(params.gene_name, fields="uniprot")

            if not result or "hits" not in result or not result["hits"]:
                return GetUniProtIdOutput(gene_name=params.gene_name, protein_uniprot_id="", found=False)

            for hit in result["hits"]:
                uniprot_data = hit.get("uniprot")
                if not uniprot_data:
                    continue

                if isinstance(uniprot_data, dict) and uniprot_data.get("Swiss-Prot"):
                    swiss_prot = uniprot_data["Swiss-Prot"]
                    uniprot_id = swiss_prot[0] if isinstance(swiss_prot, list) else str(swiss_prot)
                    return GetUniProtIdOutput(
                        gene_name=params.gene_name,
                        protein_uniprot_id=uniprot_id,
                        found=bool(uniprot_id),
                    )

                if isinstance(uniprot_data, str):
                    return GetUniProtIdOutput(
                        gene_name=params.gene_name,
                        protein_uniprot_id=uniprot_data,
                        found=True,
                    )

                if isinstance(uniprot_data, list) and uniprot_data:
                    return GetUniProtIdOutput(
                        gene_name=params.gene_name,
                        protein_uniprot_id=str(uniprot_data[0]),
                        found=True,
                    )

            return GetUniProtIdOutput(gene_name=params.gene_name, protein_uniprot_id="", found=False)
        except Exception as exc:
            logger.error("UniProt lookup failed for %s: %s", params.gene_name, exc)
            return GetUniProtIdOutput(gene_name=params.gene_name, protein_uniprot_id="", found=False)

    @staticmethod
    @function_tool
    @add_output_schema_to_docstring
    @flatten_params_from_signature
    async def save_to_database(params: SaveSequenceDataInput) -> SaveSequenceDataOutput:
        """Save extracted sequence-function data to the database."""

        logger.info("save_to_database called for gene: %s", params.gene)
        try:
            citations = [citation.model_dump(exclude_none=True) for citation in params.citations]
            async for db_session in get_db():
                sequence_id = await DatabaseService.save_sequence_data(
                    gene=params.gene,
                    protein_uniprot_id=params.protein_uniprot_id,
                    modification_type=params.modification_type,
                    interval=params.interval,
                    function=params.function,
                    effect=params.effect,
                    is_longevity_related=params.is_longevity_related,
                    longevity_association=params.longevity_association,
                    citations=citations,
                    article_url=params.article_url,
                    created_at=datetime.now(timezone.utc),
                    db_session=db_session,
                )
                return SaveSequenceDataOutput(
                    success=True,
                    sequence_id=sequence_id,
                    message=f"Successfully saved sequence-to-function data with ID: {sequence_id}",
                )
        except Exception as exc:
            logger.error("Database save failed for gene %s: %s", params.gene, exc, exc_info=True)
            return SaveSequenceDataOutput(
                success=False,
                sequence_id=None,
                message="Database save failed.",
                error=str(exc),
            )

        return SaveSequenceDataOutput(
            success=False,
            sequence_id=None,
            message="Database save failed.",
            error="Database session was not available.",
        )

    @staticmethod
    @function_tool
    @add_output_schema_to_docstring
    @flatten_params_from_signature
    def fetch_article_content(params: FetchArticleContentInput) -> ArticleContext:
        """Fetch and extract content, relevant images, and PDFs from a research article URL."""

        url = params.url
        try:

            def absolute_url(base: str, raw_url: str) -> str | None:
                if not raw_url:
                    return None
                try:
                    return urljoin(base, raw_url)
                except Exception:
                    return None

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

            extracted_text = content.get_text()
            lines = (line.strip() for line in extracted_text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            extracted_text = " ".join(chunk for chunk in chunks if chunk)
            extracted_text = re.sub(r"\s+", " ", extracted_text).strip()

            bad_extensions = (".svg", ".ico", ".gif")
            good_hints = ("figure", "fig", "graph", "plot", "gel", "western", "microscop", "blot", "supp", "supplement")
            bad_hints = ("logo", "icon", "avatar", "sprite", "banner", "ad", "advert", "cookie", "gdpr", "social", "share", "header", "footer", "nav")

            def is_relevant_image(img_tag: Any, candidate_url: str) -> bool:
                lowered_url = candidate_url.lower()
                alt = (img_tag.get("alt") or "").lower()
                css_class = " ".join(img_tag.get("class") or []).lower()
                element_id = (img_tag.get("id") or "").lower()
                if any(lowered_url.endswith(ext) for ext in bad_extensions):
                    return False
                if any(hint in lowered_url for hint in bad_hints):
                    return False
                if any(hint in alt for hint in bad_hints):
                    return False
                if any(hint in css_class for hint in bad_hints):
                    return False
                if any(hint in element_id for hint in bad_hints):
                    return False
                if any(hint in lowered_url for hint in good_hints) or any(hint in css_class for hint in good_hints):
                    return True
                return bool(alt.strip())

            image_urls: list[str] = []
            for image in soup.find_all("img"):
                src = image.get("src") or image.get("data-src")
                candidate_url = absolute_url(url, src)
                if candidate_url and is_relevant_image(image, candidate_url):
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
                text=extracted_text,
                image_urls=image_urls,
                pdf_urls=pdf_urls,
            )
        except Exception as exc:
            logger.error("Error fetching article content from %s: %s", url, exc, exc_info=True)
            return ArticleContext(article_url=url, text=None, image_urls=[], pdf_urls=[], error=str(exc))

    @staticmethod
    @function_tool
    @add_output_schema_to_docstring
    @flatten_params_from_signature
    def web_search(params: WebSearchInput) -> WebSearchOutput:
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

    @staticmethod
    @function_tool
    @add_output_schema_to_docstring
    @flatten_params_from_signature
    def vision_media(params: VisionMediaInput) -> VisionMediaOutput:
        """Analyze scientific images and PDFs for sequence-function evidence."""

        image_urls = params.image_urls[:8]
        pdf_urls = params.pdf_urls[:1]
        if not image_urls and not pdf_urls:
            return VisionMediaOutput(notes=[])

        try:
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            system_prompt = """
You are a scientific figure analyst. For each provided image or PDF:
1. Classify the media type.
2. Decide if it is relevant to sequence-function analysis.
3. Extract visible proteins, genes, sequence positions, mutations, assays, and concise claims.
Return JSON that matches the requested schema.
"""
            user_prompt = "Analyze these media URLs for sequence-function evidence."
            if params.hint:
                user_prompt += f"\nContext hint: {params.hint}"
            user_prompt += "\nImage URLs: " + json.dumps(image_urls)
            user_prompt += "\nPDF URLs: " + json.dumps(pdf_urls)

            parts: list[dict[str, Any]] = [{"type": "input_text", "text": user_prompt}]
            loaded_urls: list[tuple[str, str]] = []

            for url in image_urls:
                try:
                    parts.append({"type": "input_image", "image_url": _download_b64(url)})
                    loaded_urls.append((url, "image"))
                except Exception as exc:
                    logger.error("Failed to download image from URL %s: %s", url, exc)

            for url in pdf_urls:
                try:
                    b64_data, content_type, filename = _download_pdf_b64(url)
                    parts.append(
                        {
                            "type": "input_file",
                            "file_data": f"data:{content_type};base64,{b64_data}",
                            "filename": filename,
                        }
                    )
                    loaded_urls.append((url, "pdf"))
                except Exception as exc:
                    logger.error("Failed to download PDF from URL %s: %s", url, exc)

            if not loaded_urls:
                return VisionMediaOutput(notes=[])

            response = client.responses.create(
                model=os.getenv("STF_VISION_MODEL", "gpt-5-mini"),
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": parts},
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "VisionMediaOutput",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "notes": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "url": {"type": "string"},
                                            "kind": {"type": "string", "enum": ["image", "pdf"]},
                                            "description": {"type": "string"},
                                            "relevance": {"type": "boolean"},
                                            "relevance_score": {"type": "number"},
                                        },
                                        "required": [
                                            "url",
                                            "kind",
                                            "description",
                                            "relevance",
                                            "relevance_score",
                                        ],
                                        "additionalProperties": False,
                                    },
                                }
                            },
                            "required": ["notes"],
                            "additionalProperties": False,
                        },
                        "strict": True,
                    }
                },
            )
            data = json.loads(response.output_text or "{}")
            output = VisionMediaOutput.model_validate(data)
            return output
        except Exception as exc:
            logger.error("vision_media failed: %s", exc, exc_info=True)
            return VisionMediaOutput(notes=[])

    @staticmethod
    @function_tool
    @add_output_schema_to_docstring
    @flatten_params_from_signature
    async def execute_sql_query(params: ExecuteSQLQueryInput) -> ExecuteSQLQueryOutput:
        """Execute a read-only SQL SELECT query against sequence_data."""

        query = params.query.strip()
        logger.info("Executing SQL query: %s...", query[:100])
        if not query.lower().startswith("select"):
            return ExecuteSQLQueryOutput(
                success=False,
                query=params.query,
                results=[],
                row_count=0,
                message="Only SELECT queries are allowed.",
                error="Only SELECT queries are allowed for security reasons.",
            )

        try:
            async for db_session in get_db():
                result = await db_session.execute(text(query))
                rows = result.fetchall()
                columns = list(result.keys())
                results = [_row_to_dict(columns, row) for row in rows]
                return ExecuteSQLQueryOutput(
                    success=True,
                    query=params.query,
                    results=results,
                    row_count=len(results),
                    message=f"Query returned {len(results)} rows.",
                )
        except Exception as exc:
            logger.error("SQL query failed: %s", exc)
            return ExecuteSQLQueryOutput(
                success=False,
                query=params.query,
                results=[],
                row_count=0,
                message="Query execution failed.",
                error=str(exc),
            )

        return ExecuteSQLQueryOutput(
            success=False,
            query=params.query,
            results=[],
            row_count=0,
            message="Query execution failed.",
            error="Database session was not available.",
        )

    @staticmethod
    @function_tool
    @add_output_schema_to_docstring
    @flatten_params_from_signature
    async def find_article_records(params: FindArticleRecordsInput) -> FindArticleRecordsOutput:
        """Check whether an article URL already has parsed sequence_data records."""

        try:
            async for db_session in get_db():
                results = await DatabaseService.find_by_article_url(
                    db_session=db_session,
                    article_url=params.article_url,
                    limit=params.limit,
                )
                exists = bool(results)
                return FindArticleRecordsOutput(
                    success=True,
                    article_url=params.article_url,
                    exists=exists,
                    results=results,
                    result_count=len(results),
                    message=(
                        f"Found {len(results)} existing records for article URL."
                        if exists
                        else "No existing records found for article URL."
                    ),
                )
        except Exception as exc:
            logger.error("Article URL lookup failed: %s", exc)
            return FindArticleRecordsOutput(
                success=False,
                article_url=params.article_url,
                exists=False,
                results=[],
                result_count=0,
                message="Article URL lookup failed.",
                error=str(exc),
            )

        return FindArticleRecordsOutput(
            success=False,
            article_url=params.article_url,
            exists=False,
            results=[],
            result_count=0,
            message="Article URL lookup failed.",
            error="Database session was not available.",
        )

    @staticmethod
    @function_tool
    @add_output_schema_to_docstring
    @flatten_params_from_signature
    async def find_gene_records(params: FindGeneRecordsInput) -> FindGeneRecordsOutput:
        """Find sequence_data records by gene name or UniProt ID."""

        if not params.gene and not params.protein_uniprot_id:
            return FindGeneRecordsOutput(
                success=False,
                gene=params.gene,
                protein_uniprot_id=params.protein_uniprot_id,
                results=[],
                result_count=0,
                message="Provide at least one of gene or protein_uniprot_id.",
                error="Missing lookup key.",
            )

        try:
            async for db_session in get_db():
                results = await DatabaseService.find_by_gene_or_uniprot(
                    db_session=db_session,
                    gene=params.gene,
                    protein_uniprot_id=params.protein_uniprot_id,
                    limit=params.limit,
                )
                return FindGeneRecordsOutput(
                    success=True,
                    gene=params.gene,
                    protein_uniprot_id=params.protein_uniprot_id,
                    results=results,
                    result_count=len(results),
                    message=f"Found {len(results)} matching records.",
                )
        except Exception as exc:
            logger.error("Gene lookup failed: %s", exc)
            return FindGeneRecordsOutput(
                success=False,
                gene=params.gene,
                protein_uniprot_id=params.protein_uniprot_id,
                results=[],
                result_count=0,
                message="Gene lookup failed.",
                error=str(exc),
            )

        return FindGeneRecordsOutput(
            success=False,
            gene=params.gene,
            protein_uniprot_id=params.protein_uniprot_id,
            results=[],
            result_count=0,
            message="Gene lookup failed.",
            error="Database session was not available.",
        )


get_uniprot_id = STFTools.get_uniprot_id
save_to_database = STFTools.save_to_database
fetch_article_content = STFTools.fetch_article_content
web_search = STFTools.web_search
vision_media = STFTools.vision_media
execute_sql_query = STFTools.execute_sql_query
find_article_records = STFTools.find_article_records
find_gene_records = STFTools.find_gene_records
