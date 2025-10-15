import json
import os
from datetime import datetime
from agents import function_tool


@function_tool
def save_to_database(
    gene_protein_name: str,
    protein_sequence: str,
    dna_sequence: str,
    intervals: str,
    modifications: str,
    longevity_association: str,
    citations: str,
    article_url: str
) -> str:
    """
    Save extracted sequence-to-function data to JSON database file.
    
    Args:
        gene_protein_name: Name or ID of the gene/protein
        protein_sequence: The protein amino acid sequence
        dna_sequence: The DNA nucleotide sequence
        intervals: JSON string of sequence intervals with their functions
        modifications: JSON string of modifications and their effects
        longevity_association: Description of association with longevity/aging
        citations: JSON string of citation references
        article_url: URL of the source article
        
    Returns:
        Success message with filename
    """
    # Create data directory if it doesn't exist
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)
    
    # Parse JSON strings
    try:
        intervals_data = json.loads(intervals) if intervals else []
        modifications_data = json.loads(modifications) if modifications else []
        citations_data = json.loads(citations) if citations else []
    except json.JSONDecodeError as e:
        return f"Error parsing JSON data: {str(e)}"
    
    # Create the data structure
    data = {
        "gene_protein_name": gene_protein_name,
        "protein_sequence": protein_sequence,
        "dna_sequence": dna_sequence,
        "intervals": intervals_data,
        "modifications": modifications_data,
        "longevity_association": longevity_association,
        "citations": citations_data,
        "article_url": article_url,
        "extracted_at": datetime.now().isoformat(),
    }
    
    # Generate filename based on gene name and timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_gene_name = "".join(c for c in gene_protein_name if c.isalnum() or c in ('-', '_')).strip()
    filename = f"{safe_gene_name}_{timestamp}.json"
    filepath = os.path.join(data_dir, filename)
    
    # Save to JSON file
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return f"Successfully saved sequence-to-function data to {filepath}"


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