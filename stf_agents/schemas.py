from typing import Optional

from pydantic import BaseModel, Field


class Citation(BaseModel):
    title: Optional[str] = None
    authors: list[str] = Field(default_factory=list)
    year: Optional[int] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    raw: Optional[str] = None


class ParsingGene(BaseModel):
    gene: str
    protein_uniprot_id: str
    modification_type: str  # e.g., "deletion", "substitution"
    interval: str
    function: str
    effect: str  # effect of the modification
    is_longevity_related: bool
    longevity_association: str
    citations: list[Citation] = Field(default_factory=list)
    article_url: str


class ParsingOutput(BaseModel):
    summary: str  # Brief description of the article or answer.
    genes: list[ParsingGene] = Field(default_factory=list)
