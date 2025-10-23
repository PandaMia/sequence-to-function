import os
import re
import json
import base64
import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple
import requests
import urllib
from bs4 import BeautifulSoup
from openai import OpenAI
from agents import function_tool, WebSearchTool
from sqlalchemy import text
import mygene
from configs.database import get_db
from utils.database_service import DatabaseService
from utils.app_context import get_embedding_service
from stf_agents.schemas import ArticleContext, MediaNote

from dotenv import load_dotenv

load_dotenv()


logger = logging.getLogger(__name__)


web_search_tool = WebSearchTool(search_context_size="high")


@function_tool
def get_uniprot_id(gene_name: str) -> str:
    """
    Get UniProt Swiss-Prot ID for a given gene name using mygene service.

    Args:
        gene_name: The gene name to query (e.g., "NFE2L2", "KEAP1", "TP53")

    Returns:
        UniProt Swiss-Prot ID as string, or empty string if not found
    """
    try:
        mg = mygene.MyGeneInfo()
        res = mg.query(gene_name, fields="uniprot")

        if not res or "hits" not in res or not res["hits"]:
            return ""

        # Try to get Swiss-Prot ID from the hits
        for hit in res["hits"]:
            if "uniprot" in hit and hit["uniprot"]:
                uniprot_data = hit["uniprot"]

                # Check if it's a dict with Swiss-Prot key
                if isinstance(uniprot_data, dict) and "Swiss-Prot" in uniprot_data:
                    swiss_prot = uniprot_data["Swiss-Prot"]
                    if swiss_prot:
                        # Swiss-Prot can be a string or list
                        if isinstance(swiss_prot, list):
                            return swiss_prot[0] if swiss_prot else ""
                        else:
                            return str(swiss_prot)

                # If Swiss-Prot not available, check if uniprot is directly a string
                elif isinstance(uniprot_data, str):
                    return uniprot_data

                # If uniprot is a list, take the first one
                elif isinstance(uniprot_data, list) and uniprot_data:
                    return str(uniprot_data[0])

        return ""

    except Exception:
        return ""


@function_tool
async def save_to_database(
    gene: str,
    protein_uniprot_id: str,
    modification_type: str,
    interval: str,
    function: str,
    effect: str,
    is_longevity_related: bool,
    longevity_association: str,
    citations: str,
    article_url: str,
) -> str:
    """
    Save extracted sequence-to-function data to PostgreSQL database.

    Args:
        gene: Gene name only (e.g., "NFE2L2")
        protein_uniprot_id: UniProt ID (e.g., "Q16236")
        modification_type: Type of modification (deletion, substitution, etc.)
        interval: Amino acid position range (e.g., "AA 76–93")
        function: Description of what happens in that sequence interval
        effect: Functional consequence of the modification
        is_longevity_related: Boolean flag indicating if gene is related to longevity/aging
        longevity_association: Description of association with longevity/aging
        citations: JSON string of citation references
        article_url: URL of the source article
    All list-like fields are already typed (no JSON strings).

    Returns:
        Success message with database ID
    """
    citations_data = citations or []

    logger.info(f"save_to_database called for gene: {gene}")
    try:
        # Since this is now an async function, we can directly use async/await
        async for db_session in get_db():
            logger.info("Got database session")
            # Create created_at timestamp
            created_at = datetime.now(timezone.utc)

            logger.info(f"Calling DatabaseService.save_sequence_data for {gene}")
            sequence_id = await DatabaseService.save_sequence_data(
                gene=gene,
                protein_uniprot_id=protein_uniprot_id,
                modification_type=modification_type,
                interval=interval,
                function=function,
                effect=effect,
                is_longevity_related=is_longevity_related,
                longevity_association=longevity_association,
                citations=citations_data,
                article_url=article_url,
                created_at=created_at,
                db_session=db_session,
            )
            logger.info(f"Database save completed with ID: {sequence_id}")
            return f"Successfully saved sequence-to-function data to PostgreSQL with ID: {sequence_id}"
    except Exception as e:
        logger.error(f"Database save failed for gene {gene}: {str(e)}", exc_info=True)
        return f"Database save failed: {str(e)}"


@function_tool
def fetch_article_content(url: str) -> ArticleContext:
    """
    Fetch and extract content from a research article URL including text, images, and PDFs.
    Args:
        url: URL of the article to fetch

    Returns:
        ArticleContext object with extracted text and image URLs
    """
    try:

        def _abs(base: str, url: str) -> Optional[str]:
            if not url:
                return None
            try:
                return urllib.parse.urljoin(base, url)
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

        # Check if we were redirected to an unsupported browser page
        if "unsupported_browser" in response.url or response.status_code == 400:
            logger.warning(
                f"Detected browser compatibility issue with {url}. Trying alternative approach..."
            )
            # Try with a different, more recent User-Agent
            alternative_headers = headers.copy()
            alternative_headers["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0"
            )
            response = requests.get(
                url, headers=alternative_headers, timeout=30, allow_redirects=True
            )

        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Extract main content - try common article containers
        content_selectors = [
            "article",
            ".article-body",
            ".content",
            ".main-content",
            "#content",
            ".abstract",
            ".full-text",
        ]

        content = None
        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                content = elements[0]
                break

        if not content:
            content = soup.body or soup

        # Extract text
        text = content.get_text()

        # Clean up text
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = " ".join(chunk for chunk in chunks if chunk)

        # Remove excessive whitespace
        text = re.sub(r"\s+", " ", text).strip()

        # Extract images and PDFs - wrapped in try-except to handle blocked content
        image_urls: List[str] = []
        pdf_urls: List[str] = []

        try:
            BAD_EXT = (
                ".svg",
                ".ico",
                ".gif",
            )  # Images with these extensions are often logos or icons
            GOOD_HINTS = (
                "figure",
                "fig",
                "graph",
                "plot",
                "gel",
                "western",
                "microscop",
                "blot",
                "supp",
                "supplement",
            )
            BAD_HINTS = (
                "logo",
                "icon",
                "avatar",
                "sprite",
                "banner",
                "ad",
                "advert",
                "cookie",
                "gdpr",
                "social",
                "share",
                "header",
                "footer",
                "nav",
            )

            def is_relevant(img_tag, abs_url: str) -> bool:
                u = abs_url.lower()
                alt = (img_tag.get("alt") or "").lower()
                cls = " ".join(img_tag.get("class") or []).lower()
                _id = (img_tag.get("id") or "").lower()
                if any(u.endswith(ext) for ext in BAD_EXT):
                    return False
                if any(b in u for b in BAD_HINTS):
                    return False
                if any(b in alt for b in BAD_HINTS):
                    return False
                if any(b in cls for b in BAD_HINTS):
                    return False
                if any(b in _id for b in BAD_HINTS):
                    return False
                if any(g in u for g in GOOD_HINTS) or any(g in cls for g in GOOD_HINTS):
                    return True
                return bool(alt.strip())

            # Extract image URLs
            urls: List[str] = []
            for img in soup.find_all("img"):
                src = img.get("src") or img.get("data-src")
                if not src:
                    continue

                checked_img_url = _abs(url, src)
                if checked_img_url and is_relevant(img, checked_img_url):
                    urls.append(checked_img_url)

            image_urls = list(dict.fromkeys(urls))[:8]

            # Extract PDF URLs
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href and href.lower().endswith(".pdf"):
                    pu = _abs(url, href)
                    if pu:
                        pdf_urls.append(pu)
            pdf_urls = list(dict.fromkeys(pdf_urls))

            logger.info(
                f"Successfully extracted {len(image_urls)} images and {len(pdf_urls)} PDFs from {url}"
            )

        except Exception as img_error:
            # If image/PDF extraction fails (e.g., blocked content), log and continue with empty lists
            logger.warning(
                f"Failed to extract images/PDFs from {url}: {str(img_error)}. Continuing with text only."
            )
            image_urls = []
            pdf_urls = []

        return ArticleContext(
            article_url=url, text=text, image_urls=image_urls, pdf_urls=pdf_urls
        )

    except Exception as e:
        logger.error(
            f"Error fetching article content from {url}: {str(e)}", exc_info=True
        )
        return ArticleContext(
            article_url=url,
            text=None,
            image_urls=[],
            pdf_urls=[],
            error=str(e),
        )


def _download_b64(url: str) -> str:
    """Download an image and convert to base64 data URL. Raises exception on failure."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()

    # Validate it's actually an image
    content_type = resp.headers.get("content-type", "")
    if not content_type.startswith("image/"):
        raise ValueError(f"URL did not return an image (content-type: {content_type})")

    return "data:image/*;base64," + base64.b64encode(resp.content).decode("utf-8")


def _download_pdf_b64(url: str) -> Tuple[str, str, str]:
    """
    Download a PDF and return (base64_string, content_type, filename).
    Tries direct download and with ?download=1 parameter, validates PDF signature.
    """
    from urllib.parse import urlparse, urlunparse, urlencode, parse_qs

    session = requests.Session()

    def is_pdf_bytes(b: bytes) -> bool:
        head = b[:4096].lstrip(b"\xef\xbb\xbf\r\n\t \x00")
        return head.startswith(b"%PDF")

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
    }

    def get(u: str):
        r = session.get(u, headers=headers, timeout=60, allow_redirects=True)
        r.raise_for_status()
        ct = (r.headers.get("content-type") or "").lower()
        return r, ct

    # 1) Direct attempt
    resp, ct = get(url)
    if (
        ct.startswith("application/pdf") or ct.startswith("application/octet-stream")
    ) and is_pdf_bytes(resp.content):
        b64 = base64.b64encode(resp.content).decode("ascii")
        filename = url.split("?")[0].split("/")[-1] or "document.pdf"
        return b64, "application/pdf", filename

    # 2) Try with ?download=1 (often helps with PMC/CDN)
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs["download"] = ["1"]
    new_query = urlencode(
        {k: v[0] if len(v) == 1 else v for k, v in qs.items()}, doseq=True
    )
    url_dl = urlunparse(parsed._replace(query=new_query))

    if url_dl != url:
        resp2, ct2 = get(url_dl)
        if (
            ct2.startswith("application/pdf")
            or ct2.startswith("application/octet-stream")
        ) and is_pdf_bytes(resp2.content):
            b64 = base64.b64encode(resp2.content).decode("ascii")
            filename = url.split("?")[0].split("/")[-1] or "document.pdf"
            return b64, "application/pdf", filename

    # If we got here - it's not a PDF
    raise ValueError(f"URL did not return a PDF (content-type: {ct or 'unknown'})")


@function_tool
def vision_media(
    image_urls: list[str],
    pdf_urls: list[str],
    hint: Optional[str] = None,
    pdf_max_pages: int = 10,
) -> List[MediaNote]:
    """
    REQUIRED: Analyze images and PDFs from articles using AI vision to extract sequence data, mutations, functional assays, and structural information that may not be in text.

    Scientific figures often contain critical data like:
    - Sequence alignments showing mutations and conservation
    - Western blots and functional assays showing protein activity
    - Structural diagrams with domain annotations
    - Tables with sequence positions and modifications

    MUST be called when image_urls or pdf_urls are provided by fetch_article_content.

    Args:
        image_urls: List of image URLs from the article (from fetch_article_content result)
        pdf_urls: List of PDF URLs from the article (from fetch_article_content result)
        hint: Optional context about what to look for (e.g., "sequence modifications in KEAP1")
        pdf_max_pages: Maximum pages to analyze from PDFs (default 10)

    Returns:
        List of MediaNote objects with relevance scores and descriptions for each image/PDF
    """
    logger.info(
        f"🔍 vision_media CALLED: {len(image_urls)} images, {len(pdf_urls)} PDFs"
    )
    try:
        # Early return if no media to analyze
        if not image_urls and not pdf_urls:
            logger.warning("⚠️ vision_media: No media to analyze (empty lists)")
            return []

        # Initialize OpenAI client early
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        sys_prompt = """
            You are a scientific figure analyst.
            For each provided image/pdf:
            1) Classify its type (e.g., 'western blot', 'microscopy', 'diagram', 'logo', 'icon', 'banner').
            2) Decide if the image is relevant to sequence-function analysis (relevance: true/false).
            3) Provide a relevance_score in [0.0, 1.0] and a short reason.
            4) If relevant, provide details about:
            - proteins, modifications (with positions if visible),
            - concise OCR-like summary (ocr_text),
            - 1-3 concise claims.
            Return one JSON object per input image (same order), with the schema ImageNotes.
            If not relevant, still return the object with relevance=false, relevance_score, reason, and image_url; leave other fields empty.
        """
        user_prompt = "Analyze provided files for sequence-function evidence."
        if hint:
            user_prompt += f" Context hint: {hint}"

        parts = [{"type": "input_text", "text": user_prompt}]
        successful_images = 0
        successful_pdfs = 0

        # Process image URLs (download and convert to base64)
        if image_urls:
            for url in image_urls:
                try:
                    parts.append(
                        {"type": "input_image", "image_url": _download_b64(url)}
                    )
                    successful_images += 1
                    logger.info(f"Successfully loaded image: {url}")
                except Exception as e:
                    logger.error(
                        "Failed to download image from URL: %s, error: %s", url, str(e)
                    )

        # Process PDF URLs using ResponseInputFileParam structure with base64
        if pdf_urls:
            for url in pdf_urls:
                try:
                    b64_data, content_type, filename = _download_pdf_b64(url)
                    # Ensure all values are strings, not bytes
                    file_data_str = f"data:{content_type};base64,{b64_data}"
                    parts.append(
                        {
                            "type": "input_file",
                            "file_data": file_data_str,
                            "filename": str(filename),
                        }
                    )
                    successful_pdfs += 1
                    logger.info(f"Successfully added PDF: {url} ({filename})")
                except Exception as e:
                    logger.error(
                        "Failed to add PDF from URL: %s, error: %s", url, str(e)
                    )

        # If no images or PDFs were successfully loaded, return empty list
        if successful_images == 0 and successful_pdfs == 0:
            logger.warning("No images or PDFs successfully loaded for vision analysis")
            return []

        logger.info(
            f"Analyzing {successful_images} images and {successful_pdfs} PDFs with vision API"
        )

        # Debug: log the structure of parts to identify any bytes objects
        for i, part in enumerate(parts):
            part_type = part.get("type", "unknown")
            if part_type == "input_file":
                logger.debug(
                    f"Part {i}: type={part_type}, filename={part.get('filename')}, file_data_len={len(part.get('file_data', ''))}"
                )
            else:
                logger.debug(f"Part {i}: type={part_type}")

        notes: List[MediaNote] = []

        resp = client.responses.create(
            model="gpt-5-mini",
            input=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": parts},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "ImageNotes",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "notes": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "url": {"type": "string"},
                                        "kind": {
                                            "type": "string",
                                            "enum": ["image", "pdf"],
                                        },
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

        data = json.loads(resp.output_text or "{}")
        items = data.get("notes", [])
        for it in items:
            notes.append(
                MediaNote(
                    url=it["url"],
                    kind=it["kind"],
                    description=it["description"],
                    relevance=it["relevance"],
                    relevance_score=float(it["relevance_score"]),
                )
            )
        return notes
    except Exception as e:
        logger.error(f"vision_media failed: {str(e)}", exc_info=True)
        return []


@function_tool
async def execute_sql_query(query: str) -> str:
    """
    Execute a SQL query against the sequence-to-function database.

    Args:
        query: SQL query to execute (SELECT statements only)

    Returns:
        Query results formatted as JSON string
    """
    logger.info(f"Executing SQL query: {query[:100]}...")

    # Security check - only allow SELECT queries
    query_lower = query.lower().strip()
    if not query_lower.startswith("select"):
        return "Error: Only SELECT queries are allowed for security reasons"

    try:
        async for db_session in get_db():
            result = await db_session.execute(text(query))
            rows = result.fetchall()

            if not rows:
                return "No results found for the query"

            # Convert rows to list of dictionaries, filtering out embedding field
            columns = result.keys()
            results = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    # Skip embedding field - it's for internal use only
                    if col.lower() == "embedding":
                        continue

                    value = row[i]
                    # Handle JSON fields
                    if isinstance(value, (dict, list)):
                        row_dict[col] = value
                    else:
                        row_dict[col] = str(value) if value is not None else None
                results.append(row_dict)

            logger.info(f"Query returned {len(results)} rows")
            return json.dumps(results, indent=2, default=str)

    except Exception as e:
        logger.error(f"SQL query failed: {str(e)}")
        return f"Query execution failed: {str(e)}"


@function_tool
async def semantic_search(
    query: str, limit: int = 5, min_similarity: float = 0.5
) -> str:
    """
    Perform semantic search on sequence data using vector similarity.

    This searches for genes/proteins that are semantically similar to the query,
    even if they don't contain the exact keywords.

    Args:
        query: Natural language search query (e.g., "genes related to oxidative stress response")
        limit: Maximum number of results to return (default: 5, max: 20)
        min_similarity: Minimum similarity threshold from 0.0 to 1.0 (default: 0.5)
                       Only results with similarity >= this value will be returned.
                       Higher values (0.7-0.9) = more strict, only very similar results
                       Lower values (0.3-0.5) = more lenient, broader results

    Returns:
        JSON string with similar sequence data records and similarity scores
    """
    logger.info(
        f"🔍 SEMANTIC SEARCH - Query: {query[:100]}... (limit: {limit}, min_similarity: {min_similarity})"
    )

    # Validate parameters
    if limit < 1:
        limit = 5
    if limit > 20:
        limit = 20

    # Validate similarity threshold
    if min_similarity < 0.0:
        min_similarity = 0.0
    if min_similarity > 1.0:
        min_similarity = 1.0

    # Get embedding service from app context
    embedding_service = get_embedding_service()
    if not embedding_service:
        error_msg = (
            "Error: Embedding service not available. Cannot perform semantic search."
        )
        logger.error(f"❌ {error_msg}")
        return error_msg

    try:
        # Generate embedding for the query
        logger.info(f"📊 Generating embedding for query...")
        query_embedding = await embedding_service.generate_embedding(query)
        if not query_embedding:
            error_msg = "Error: Failed to generate embedding for the query"
            logger.error(f"❌ {error_msg}")
            return error_msg

        logger.info(
            f"✅ Embedding generated successfully! Dimensions: {len(query_embedding)}"
        )

        # Perform similarity search using cosine distance with threshold
        logger.info(f"🔎 Executing vector similarity search in PostgreSQL...")
        async for db_session in get_db():
            sql_query = text(
                """
                SELECT
                    id,
                    gene,
                    protein_uniprot_id,
                    modification_type,
                    interval,
                    function,
                    effect,
                    is_longevity_related,
                    longevity_association,
                    citations,
                    article_url,
                    1 - (embedding <=> :query_embedding) as similarity
                FROM sequence_data
                WHERE embedding IS NOT NULL
                    AND (1 - (embedding <=> :query_embedding)) >= :min_similarity
                ORDER BY embedding <=> :query_embedding
                LIMIT :limit
            """
            )

            logger.info(
                f"Executing pgvector similarity search with limit {limit}, min_similarity {min_similarity}"
            )
            result = await db_session.execute(
                sql_query,
                {
                    "query_embedding": str(query_embedding),
                    "limit": limit,
                    "min_similarity": min_similarity,
                },
            )
            rows = result.fetchall()
            logger.info(
                f"✅ Query executed! Found {len(rows)} results (min similarity: {min_similarity})"
            )

            if not rows:
                return json.dumps(
                    {
                        "message": f"No results found with similarity >= {min_similarity}. Try lowering min_similarity or check if database has records with embeddings.",
                        "query": query,
                        "min_similarity": min_similarity,
                        "results": [],
                    }
                )

            # Convert to list of dictionaries, filtering out embedding field
            columns = result.keys()
            results = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    # Skip embedding field - it's for internal use only
                    if col.lower() == "embedding":
                        continue

                    value = row[i]
                    if isinstance(value, (dict, list)):
                        row_dict[col] = value
                    elif col == "similarity":
                        # Format similarity as percentage
                        row_dict[col] = f"{float(value) * 100:.2f}%"
                    else:
                        row_dict[col] = str(value) if value is not None else None
                results.append(row_dict)

            logger.info(f"Semantic search returned {len(results)} results")
            return json.dumps(results, indent=2, default=str)

    except Exception as e:
        logger.error(f"Semantic search failed: {str(e)}")
        return f"Semantic search failed: {str(e)}"
