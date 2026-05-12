"""Database-backed tool logic for STF tools."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import text

from configs.database import get_db
from tools.schemas import (
    ExecuteSQLQueryInput,
    ExecuteSQLQueryOutput,
    FindArticleRecordsInput,
    FindArticleRecordsOutput,
    FindGeneRecordsInput,
    FindGeneRecordsOutput,
    SaveSequenceDataInput,
    SaveSequenceDataOutput,
)
from utils.database_service import DatabaseService
from utils.stf_tool_utils import row_to_dict


logger = logging.getLogger(__name__)


async def save_to_database_logic(params: SaveSequenceDataInput) -> SaveSequenceDataOutput:
    """Save extracted sequence-function data to the database."""

    logger.info("save_to_database called for gene: %s", params.gene)
    try:
        citations = [citation.model_dump(exclude_none=True) for citation in params.citations]
        async for db_session in get_db():
            sequence_id = await DatabaseService.save_sequence_data(
                gene=params.gene,
                protein_uniprot_id=params.protein_uniprot_id,
                modification_type=params.modification_type,
                interval=params.interval,
                function=params.function,
                effect=params.effect,
                is_longevity_related=params.is_longevity_related,
                longevity_association=params.longevity_association,
                citations=citations,
                article_url=params.article_url,
                article_text=params.article_text,
                created_at=datetime.now(timezone.utc),
                db_session=db_session,
            )
            return SaveSequenceDataOutput(
                success=True,
                sequence_id=sequence_id,
                message=f"Successfully saved sequence-to-function data with ID: {sequence_id}",
            )
    except Exception as exc:
        logger.error("Database save failed for gene %s: %s", params.gene, exc, exc_info=True)
        return SaveSequenceDataOutput(
            success=False,
            sequence_id=None,
            message="Database save failed.",
            error=str(exc),
        )

    return SaveSequenceDataOutput(
        success=False,
        sequence_id=None,
        message="Database save failed.",
        error="Database session was not available.",
    )


async def execute_sql_query_logic(params: ExecuteSQLQueryInput) -> ExecuteSQLQueryOutput:
    """Execute a read-only SQL SELECT query against the STF database."""

    query = params.query.strip()
    logger.info("Executing SQL query: %s...", query[:100])
    if not query.lower().startswith("select"):
        return ExecuteSQLQueryOutput(
            success=False,
            query=params.query,
            results=[],
            row_count=0,
            message="Only SELECT queries are allowed.",
            error="Only SELECT queries are allowed for security reasons.",
        )

    try:
        async for db_session in get_db():
            result = await db_session.execute(text(query))
            rows = result.fetchall()
            columns = list(result.keys())
            results = [row_to_dict(columns, row) for row in rows]
            return ExecuteSQLQueryOutput(
                success=True,
                query=params.query,
                results=results,
                row_count=len(results),
                message=f"Query returned {len(results)} rows.",
            )
    except Exception as exc:
        logger.error("SQL query failed: %s", exc)
        return ExecuteSQLQueryOutput(
            success=False,
            query=params.query,
            results=[],
            row_count=0,
            message="Query execution failed.",
            error=str(exc),
        )

    return ExecuteSQLQueryOutput(
        success=False,
        query=params.query,
        results=[],
        row_count=0,
        message="Query execution failed.",
        error="Database session was not available.",
    )


async def find_article_records_logic(params: FindArticleRecordsInput) -> FindArticleRecordsOutput:
    """Check whether an article URL already has parsed sequence-function records."""

    try:
        async for db_session in get_db():
            results = await DatabaseService.find_by_article_url(
                db_session=db_session,
                article_url=params.article_url,
                limit=params.limit,
            )
            exists = bool(results)
            return FindArticleRecordsOutput(
                success=True,
                article_url=params.article_url,
                exists=exists,
                results=results,
                result_count=len(results),
                message=(
                    f"Found {len(results)} existing records for article URL."
                    if exists
                    else "No existing records found for article URL."
                ),
            )
    except Exception as exc:
        logger.error("Article URL lookup failed: %s", exc)
        return FindArticleRecordsOutput(
            success=False,
            article_url=params.article_url,
            exists=False,
            results=[],
            result_count=0,
            message="Article URL lookup failed.",
            error=str(exc),
        )

    return FindArticleRecordsOutput(
        success=False,
        article_url=params.article_url,
        exists=False,
        results=[],
        result_count=0,
        message="Article URL lookup failed.",
        error="Database session was not available.",
    )


async def find_gene_records_logic(params: FindGeneRecordsInput) -> FindGeneRecordsOutput:
    """Find sequence-function records by gene name or UniProt ID."""

    if not params.gene and not params.protein_uniprot_id:
        return FindGeneRecordsOutput(
            success=False,
            gene=params.gene,
            protein_uniprot_id=params.protein_uniprot_id,
            results=[],
            result_count=0,
            message="Provide at least one of gene or protein_uniprot_id.",
            error="Missing lookup key.",
        )

    try:
        async for db_session in get_db():
            results = await DatabaseService.find_by_gene_or_uniprot(
                db_session=db_session,
                gene=params.gene,
                protein_uniprot_id=params.protein_uniprot_id,
                limit=params.limit,
            )
            return FindGeneRecordsOutput(
                success=True,
                gene=params.gene,
                protein_uniprot_id=params.protein_uniprot_id,
                results=results,
                result_count=len(results),
                message=f"Found {len(results)} matching records.",
            )
    except Exception as exc:
        logger.error("Gene lookup failed: %s", exc)
        return FindGeneRecordsOutput(
            success=False,
            gene=params.gene,
            protein_uniprot_id=params.protein_uniprot_id,
            results=[],
            result_count=0,
            message="Gene lookup failed.",
            error=str(exc),
        )

    return FindGeneRecordsOutput(
        success=False,
        gene=params.gene,
        protein_uniprot_id=params.protein_uniprot_id,
        results=[],
        result_count=0,
        message="Gene lookup failed.",
        error="Database session was not available.",
    )
