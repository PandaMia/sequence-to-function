import json
import logging
from datetime import datetime, timezone
from agents import function_tool
from sqlalchemy import text
from configs.database import get_db
from utils.database_service import DatabaseService
from utils.embeddings import create_search_text
from utils.app_context import get_embedding_service
import mygene


logger = logging.getLogger(__name__)


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
    article_url: str
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
        
    Returns:
        Success message with database ID
    """
    # Parse JSON strings
    try:
        citations_data = json.loads(citations) if citations else []
    except json.JSONDecodeError as e:
        return f"Error parsing JSON data: {str(e)}"
    
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
                db_session=db_session
            )
            logger.info(f"Database save completed with ID: {sequence_id}")
            return f"Successfully saved sequence-to-function data to PostgreSQL with ID: {sequence_id}"
    except Exception as e:
        logger.error(f"Database save failed for gene {gene}: {str(e)}", exc_info=True)
        return f"Database save failed: {str(e)}"


@function_tool
def fetch_article_content(url: str) -> str:
    """
    Fetch and extract content from a research article URL.
    
    Args:
        url: URL of the article to fetch
        
    Returns:
        Extracted text content from the article
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
        
        return text
        
    except Exception as e:
        return f"Error fetching article: {str(e)}"


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
            
            # Convert rows to list of dictionaries, filtering out embedding field
            columns = result.keys()
            results = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    # Skip embedding field - it's for internal use only
                    if col.lower() == 'embedding':
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
    query: str,
    limit: int = 5,
    min_similarity: float = 0.5
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
    logger.info(f"🔍 SEMANTIC SEARCH - Query: {query[:100]}... (limit: {limit}, min_similarity: {min_similarity})")

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
        error_msg = "Error: Embedding service not available. Cannot perform semantic search."
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

        logger.info(f"✅ Embedding generated successfully! Dimensions: {len(query_embedding)}")
        
        # Perform similarity search using cosine distance with threshold
        logger.info(f"🔎 Executing vector similarity search in PostgreSQL...")
        async for db_session in get_db():
            sql_query = text("""
                SELECT
                    id,
                    gene,
                    protein_uniprot_id,
                    interval,
                    function,
                    modification_type,
                    effect,
                    longevity_association,
                    citations,
                    article_url,
                    1 - (embedding <=> :query_embedding) as similarity
                FROM sequence_data
                WHERE embedding IS NOT NULL
                    AND (1 - (embedding <=> :query_embedding)) >= :min_similarity
                ORDER BY embedding <=> :query_embedding
                LIMIT :limit
            """)

            logger.info(f"Executing pgvector similarity search with limit {limit}, min_similarity {min_similarity}")
            result = await db_session.execute(
                sql_query,
                {
                    "query_embedding": str(query_embedding),
                    "limit": limit,
                    "min_similarity": min_similarity
                }
            )
            rows = result.fetchall()
            logger.info(f"✅ Query executed! Found {len(rows)} results (min similarity: {min_similarity})")

            if not rows:
                return json.dumps({
                    "message": f"No results found with similarity >= {min_similarity}. Try lowering min_similarity or check if database has records with embeddings.",
                    "query": query,
                    "min_similarity": min_similarity,
                    "results": []
                })

            # Convert to list of dictionaries, filtering out embedding field
            columns = result.keys()
            results = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    # Skip embedding field - it's for internal use only
                    if col.lower() == 'embedding':
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