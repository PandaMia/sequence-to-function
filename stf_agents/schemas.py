from pydantic import BaseModel
from typing import List, Optional

class Citation(BaseModel):
    title: str
    authors: List[str] = []
    year: Optional[int] = None
    doi: Optional[str] = None
    url: Optional[str] = None

class ParsingOutput(BaseModel):
    gene: str
    protein_uniprot_id: str
    interval: str
    function: str
    modification_type: str # e.g., "deletion", "substitution"
    effect: str # effect of the modification
    longevity_association: str
    citations: List[Citation] = []
    article_url: str

class ArticleContext(BaseModel):
    article_url: Optional[str] = None
    text: Optional[str]
    image_urls: List[str] = []
    pdf_urls: List[str] = []
    error: Optional[str] = None

class MediaNote(BaseModel):
    url: str               
    kind: str   # "image" | "pdf"
    description: str       # summary or caption
    relevance: bool = True
    relevance_score: float = 1.0