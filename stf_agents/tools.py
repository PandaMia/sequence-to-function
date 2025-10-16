import json
import os
import asyncio
from datetime import datetime
from agents import function_tool
from configs.database import get_db
from utils.database_service import DatabaseService


@function_tool
def save_to_database(
    gene_protein_name: str,
    protein_sequence: str,
    dna_sequence: str,
    intervals: str,
    modifications: str,
    longevity_association: str,
    citations: str,
    article_url: str,
    session_id: str = None,
    model_name: str = "unknown"
) -> str:
    """
    Save extracted sequence-to-function data to PostgreSQL database.
    
    Args:
        gene_protein_name: Name or ID of the gene/protein
        protein_sequence: The protein amino acid sequence
        dna_sequence: The DNA nucleotide sequence
        intervals: JSON string of sequence intervals with their functions
        modifications: JSON string of modifications and their effects
        longevity_association: Description of association with longevity/aging
        citations: JSON string of citation references
        article_url: URL of the source article
        session_id: Optional session ID for tracking
        model_name: Name of the AI model used for extraction
        
    Returns:
        Success message with database ID
    """
    # Parse JSON strings
    try:
        intervals_data = json.loads(intervals) if intervals else []
        modifications_data = json.loads(modifications) if modifications else []
        citations_data = json.loads(citations) if citations else []
    except json.JSONDecodeError as e:
        return f"Error parsing JSON data: {str(e)}"
    
    # Create the data structure
    extraction_data = {
        "gene_protein_name": gene_protein_name,
        "protein_sequence": protein_sequence,
        "dna_sequence": dna_sequence,
        "intervals": intervals_data,
        "modifications": modifications_data,
        "longevity_association": longevity_association,
        "citations": citations_data,
        "extracted_at": datetime.now().isoformat(),
    }
    
    # Save to PostgreSQL database
    async def _save_to_postgres():
        try:
            async for db_session in get_db():
                extraction_id = await DatabaseService.save_extraction(
                    session_id=session_id or f"tool_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    article_link=article_url,
                    extraction_data=extraction_data,
                    model_name=model_name,
                    db_session=db_session
                )
                return extraction_id
        except Exception as e:
            raise e
    
    try:
        # Run the async function
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, we need to handle this differently
            return "Database save queued - will be processed asynchronously"
        else:
            extraction_id = loop.run_until_complete(_save_to_postgres())
            return f"Successfully saved sequence-to-function data to PostgreSQL with ID: {extraction_id}"
    except Exception as e:
        # Fallback to JSON file if database fails
        data_dir = "data"
        os.makedirs(data_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_gene_name = "".join(c for c in gene_protein_name if c.isalnum() or c in ('-', '_')).strip()
        filename = f"{safe_gene_name}_{timestamp}.json"
        filepath = os.path.join(data_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(extraction_data, f, indent=2, ensure_ascii=False)
        
        return f"Database save failed ({str(e)}), saved to fallback file: {filepath}"


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