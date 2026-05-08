"""Pydantic schemas for STF function tools."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ToolCitation(BaseModel):
    """Citation payload accepted by database persistence tools."""

    title: Optional[str] = Field(default=None, description="Citation title when available.")
    authors: list[str] = Field(default_factory=list, description="Citation authors.")
    year: Optional[int] = Field(default=None, description="Publication year.")
    doi: Optional[str] = Field(default=None, description="Citation DOI.")
    url: Optional[str] = Field(default=None, description="Citation source URL.")
    raw: Optional[str] = Field(default=None, description="Raw citation text when parsed fields are unavailable.")


class GetUniProtIdInput(BaseModel):
    gene_name: str = Field(..., description="Gene symbol to resolve, for example NFE2L2, KEAP1, or TP53.")


class GetUniProtIdOutput(BaseModel):
    gene_name: str = Field(..., description="Gene symbol that was queried.")
    protein_uniprot_id: str = Field(default="", description="Resolved UniProt Swiss-Prot ID.")
    found: bool = Field(..., description="True when a UniProt ID was found.")


class SaveSequenceDataInput(BaseModel):
    gene: str = Field(..., description="Gene symbol only, for example NFE2L2.")
    protein_uniprot_id: str = Field(default="", description="UniProt ID for the encoded protein.")
    modification_type: str = Field(default="", description="Modification type such as deletion or substitution.")
    interval: str = Field(default="", description='Amino acid interval in the exact format "AA 76-93".')
    function: str = Field(default="", description="Function associated with the interval or gene.")
    effect: str = Field(default="", description="Functional consequence of the modification.")
    is_longevity_related: bool = Field(default=False, description="Whether the gene is related to aging or longevity.")
    longevity_association: str = Field(default="", description="Evidence-backed aging or longevity association.")
    citations: list[ToolCitation] = Field(default_factory=list, description="Source citations.")
    article_url: str = Field(default="", description="Source article URL.")


class SaveSequenceDataOutput(BaseModel):
    success: bool = Field(..., description="True when the database save succeeded.")
    sequence_id: Optional[int] = Field(default=None, description="Database record ID when saved.")
    message: str = Field(..., description="Human-readable status message.")
    error: Optional[str] = Field(default=None, description="Error details when saving failed.")


class FetchArticleContentInput(BaseModel):
    url: str = Field(..., description="Research article URL to fetch and parse.")


class ArticleContext(BaseModel):
    article_url: Optional[str] = Field(default=None, description="Fetched article URL.")
    text: Optional[str] = Field(default=None, description="Extracted article text.")
    image_urls: list[str] = Field(default_factory=list, description="Relevant image URLs found in the article.")
    pdf_urls: list[str] = Field(default_factory=list, description="PDF URLs found in the article.")
    error: Optional[str] = Field(default=None, description="Fetch or parsing error, if any.")


class WebSearchInput(BaseModel):
    query: str = Field(..., description="Search query or URL to retrieve supporting article content.")


class WebSearchOutput(BaseModel):
    success: bool = Field(..., description="True when search content was returned.")
    query: str = Field(..., description="Search query that was executed.")
    content: str = Field(default="", description="Search result summary or retrieved page content.")
    error: Optional[str] = Field(default=None, description="Search error, if any.")


class VisionMediaInput(BaseModel):
    image_urls: list[str] = Field(default_factory=list, description="Image URLs to analyze. Maximum 8.")
    pdf_urls: list[str] = Field(default_factory=list, description="PDF URLs to analyze. Maximum 1.")
    hint: Optional[str] = Field(default=None, description="Optional context about what to look for.")
    pdf_max_pages: int = Field(default=10, ge=1, le=50, description="Maximum PDF pages to analyze.")


class MediaNote(BaseModel):
    url: str = Field(..., description="Analyzed media URL.")
    kind: Literal["image", "pdf"] = Field(..., description="Media type.")
    description: str = Field(..., description="Concise scientific description of the relevant content.")
    relevance: bool = Field(default=True, description="Whether the media is relevant to sequence-function analysis.")
    relevance_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Relevance score from 0 to 1.")


class VisionMediaOutput(BaseModel):
    notes: list[MediaNote] = Field(default_factory=list, description="Vision analysis notes.")


class ExecuteSQLQueryInput(BaseModel):
    query: str = Field(..., description="Read-only SELECT query against the sequence_data table.")


class ExecuteSQLQueryOutput(BaseModel):
    success: bool = Field(..., description="True when the query executed successfully.")
    query: str = Field(..., description="SQL query that was executed.")
    results: list[dict[str, Any]] = Field(default_factory=list, description="Rows returned by the query.")
    row_count: int = Field(default=0, description="Number of returned rows.")
    message: str = Field(default="", description="Human-readable result message.")
    error: Optional[str] = Field(default=None, description="Query error, if any.")


class FindArticleRecordsInput(BaseModel):
    article_url: str = Field(..., description="Article URL to check for existing parsed records.")
    limit: int = Field(default=100, ge=1, le=500, description="Maximum number of records to return.")


class FindArticleRecordsOutput(BaseModel):
    success: bool = Field(..., description="True when the lookup executed successfully.")
    article_url: str = Field(..., description="Article URL that was checked.")
    exists: bool = Field(..., description="True when records already exist for this URL.")
    results: list[dict[str, Any]] = Field(default_factory=list, description="Existing sequence_data rows for this URL.")
    result_count: int = Field(default=0, description="Number of existing records.")
    message: str = Field(default="", description="Human-readable result message.")
    error: Optional[str] = Field(default=None, description="Lookup error, if any.")


class FindGeneRecordsInput(BaseModel):
    gene: Optional[str] = Field(default=None, description="Gene symbol to search for.")
    protein_uniprot_id: Optional[str] = Field(default=None, description="UniProt ID to search for.")
    limit: int = Field(default=100, ge=1, le=500, description="Maximum number of records to return.")


class FindGeneRecordsOutput(BaseModel):
    success: bool = Field(..., description="True when the lookup executed successfully.")
    gene: Optional[str] = Field(default=None, description="Gene symbol that was searched.")
    protein_uniprot_id: Optional[str] = Field(default=None, description="UniProt ID that was searched.")
    results: list[dict[str, Any]] = Field(default_factory=list, description="Matching sequence_data rows.")
    result_count: int = Field(default=0, description="Number of matching records.")
    message: str = Field(default="", description="Human-readable result message.")
    error: Optional[str] = Field(default=None, description="Lookup error, if any.")
