from pydantic import BaseModel
from typing import List, Optional

class Interval(BaseModel):
    start: int
    end: int
    function: str
    evidence: List[str] = []

class Modification(BaseModel):
    type: str
    position: Optional[int] = None
    effect: Optional[str] = None

class Citation(BaseModel):
    title: str
    authors: List[str] = []
    year: Optional[int] = None
    doi: Optional[str] = None
    url: Optional[str] = None

class ParsingOutput(BaseModel):
    gene_protein_name: str
    protein_sequence: Optional[str] = None
    dna_sequence: Optional[str] = None
    intervals: List[Interval] = []
    modifications: List[Modification] = []
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

class ArticleContext(BaseModel):
    article_url: Optional[str] = None
    text: Optional[str]
    image_urls: List[str] = []
    figures: List[FigureFinding] = []
    error: Optional[str] = None