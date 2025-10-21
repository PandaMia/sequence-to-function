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
    protein_uniprot_id: Optional[str] = None
    interval: Optional[str] = None
    function: Optional[str] = None
    modification_type: Optional[str] = None # e.g., "deletion", "substitution"
    effect: Optional[str] = None # effect of the modification
    longevity_association: Optional[str] = None
    citations: List[Citation] = []
    article_url: Optional[str] = None

class FigureFinding(BaseModel):
    figure_id: str
    image_url: str
    caption: Optional[str] = None
    ocr_text: Optional[str] = None
    proteins: List[str] = []
    modifications: List[str] = []
    positions: List[int] = []
    claims: List[str] = []
    relevance: bool = True
    relevance_score: float = 1.0
    reasoning: Optional[str] = None
    kind: Optional[str] = None # e.g. "gel", "diagram", "logo", "icon"

class ArticleContext(BaseModel):
    article_url: Optional[str] = None
    text: Optional[str]
    image_urls: List[str] = []
    figures: List[FigureFinding] = []
    error: Optional[str] = None