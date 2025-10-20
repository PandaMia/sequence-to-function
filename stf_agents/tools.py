import json
import logging
from datetime import datetime, timezone
import urllib
from agents import function_tool
from sqlalchemy import text
from configs.database import get_db
from stf_agents.subagents.vision_agent import vision_agent_process_images
from utils.database_service import DatabaseService
from typing import List, Optional
from .schemas import Interval, Modification, Citation, ArticleContext, FigureFinding


logger = logging.getLogger(__name__)

MAX_URLS = 8

def _abs_url(base: str, url: str) -> Optional[str]:
    if not url:
        return None
    try:
        return urllib.parse.urljoin(base, url)
    except Exception:
        return None


@function_tool
async def save_to_database(
    gene_protein_name: str,
    protein_sequence: str | None,
    dna_sequence: str | None,
    intervals: List[Interval],
    modifications: List[Modification],
    longevity_association: str | None,
    citations: List[Citation],
    article_url: str | None,
) -> str:
    """
    Save extracted sequence-to-function data to PostgreSQL database.
    All list-like fields are already typed (no JSON strings).
    Returns success message with DB ID.
    """
    # Parse JSON strings
    intervals_data = intervals or []
    modifications_data = modifications or []
    citations_data = citations or []

    logger.info(f"save_to_database called for gene: {gene_protein_name}")
    
    try:
        # Since this is now an async function, we can directly use async/await
        async for db_session in get_db():
            logger.info("Got database session")
            # Create extracted_at timestamp
            extracted_at = datetime.now(timezone.utc)
            
            logger.info(f"Calling DatabaseService.save_sequence_data for {gene_protein_name}")
            sequence_id = await DatabaseService.save_sequence_data(
                gene_protein_name=gene_protein_name,
                protein_sequence=protein_sequence,
                dna_sequence=dna_sequence,
                intervals=intervals_data,
                modifications=modifications_data,
                longevity_association=longevity_association,
                citations=citations_data,
                article_url=article_url,
                extracted_at=extracted_at,
                db_session=db_session
            )
            logger.info(f"Database save completed with ID: {sequence_id}")
            return f"Successfully saved sequence-to-function data to PostgreSQL with ID: {sequence_id}"
    except Exception as e:
        logger.error(f"Database save failed for gene {gene_protein_name}: {str(e)}", exc_info=True)
        return f"Database save failed: {str(e)}"


@function_tool
def fetch_article_content(url: str, user_request: str, analyze_images: bool = False) -> ArticleContext:
    """
    Fetch and extract content from a research article URL.
    
    Args:
        url: URL of the article to fetch
        user_request: Original user request for context in parsing
        analyze_images: Whether to analyze images in the article
    Returns:
        ArticleContext object with extracted text and image URLs
    """
    try:
        import requests
        from bs4 import BeautifulSoup
        import re
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Extract main content - try common article containers
        content_selectors = [
            'article',
            '.article-body',
            '.content',
            '.main-content',
            '#content',
            '.abstract',
            '.full-text'
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
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        # Extract image URLs
        urls: List[str] = []
        for img in soup.find_all('img'):
            img_url = img.get('src')  or img.get("data-src") or ""
            if img_url:
                checked_img_url = _abs_url(url, img_url)
                if checked_img_url:
                    urls.append(checked_img_url)

        seen_urls = set()
        unique_urls = []
        for u in urls:
            if u not in seen_urls:
                seen_urls.add(u)
                unique_urls.append(u)
            if len(unique_urls) >= MAX_URLS:
                break
        figures: List[FigureFinding] = []
        if unique_urls and analyze_images:
            figs = vision_agent_process_images(unique_urls, hint=user_request)
            figures = figs or []
            text += "\n\n[ANALYZED IMAGES]:\n" + "\n".join(analyze_images)
        article_context = ArticleContext(
            article_url=url,
            text=text,
            image_urls=unique_urls,
            figures=figures
        )
        return article_context

    except Exception as e:
        logger.error(f"Error fetching article content from {url}: {str(e)}", exc_info=True)
        return ArticleContext(
            article_url=url,
            text=None,
            image_urls=[],
            figures=[],
            error=str(e),
        )


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
    if not query_lower.startswith('select'):
        return "Error: Only SELECT queries are allowed for security reasons"
    
    try:
        async for db_session in get_db():
            result = await db_session.execute(text(query))
            rows = result.fetchall()
            
            if not rows:
                return "No results found for the query"
            
            # Convert rows to list of dictionaries
            columns = result.keys()
            results = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
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