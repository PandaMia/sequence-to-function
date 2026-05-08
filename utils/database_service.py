from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from configs.config import CSV_FILE_PATH, CSV_HEADERS
from configs.database import SequenceData, get_db


logger = logging.getLogger(__name__)


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _parse_citations(value: Any) -> list:
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
        return []

    parsed = value
    for _ in range(2):
        if not isinstance(parsed, str):
            break
        try:
            parsed = json.loads(parsed)
        except Exception:
            return [{"raw": parsed}]

    return parsed if isinstance(parsed, list) else [{"raw": str(parsed)}]


class DatabaseService:
    @staticmethod
    def sequence_data_to_dict(record: SequenceData) -> dict[str, Any]:
        return {
            "id": record.id,
            "gene": record.gene,
            "protein_uniprot_id": record.protein_uniprot_id,
            "modification_type": record.modification_type,
            "interval": record.interval,
            "function": record.function,
            "effect": record.effect,
            "is_longevity_related": record.is_longevity_related,
            "longevity_association": record.longevity_association,
            "citations": record.citations or [],
            "article_url": record.article_url,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        }

    @staticmethod
    async def save_sequence_data(
        gene: str,
        protein_uniprot_id: str,
        modification_type: str,
        interval: str,
        function: str,
        effect: str,
        is_longevity_related: bool,
        longevity_association: str,
        citations: list,
        article_url: str,
        created_at: datetime,
        db_session: AsyncSession,
        export_to_csv: bool = True,
    ) -> int:
        """Save sequence data to the database."""

        try:
            sequence_data = SequenceData(
                gene=gene,
                protein_uniprot_id=protein_uniprot_id,
                modification_type=modification_type,
                interval=interval,
                function=function,
                effect=effect,
                is_longevity_related=is_longevity_related,
                longevity_association=longevity_association,
                citations=citations,
                article_url=article_url,
                created_at=created_at,
            )

            db_session.add(sequence_data)
            await db_session.commit()
            await db_session.refresh(sequence_data)

            if export_to_csv:
                await DatabaseService.export_to_csv(CSV_FILE_PATH, db_session)

            logger.info("Saved sequence data with ID %s for gene %s", sequence_data.id, gene)
            return sequence_data.id
        except Exception:
            await db_session.rollback()
            logger.exception("Error saving sequence data for gene %s", gene)
            raise

    @staticmethod
    async def get_all_sequence_data(
        db_session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SequenceData]:
        """Get all sequence data records with pagination."""

        try:
            result = await db_session.execute(
                select(SequenceData)
                .order_by(SequenceData.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            return list(result.scalars().all())
        except Exception:
            logger.exception("Error retrieving sequence data")
            return []

    @staticmethod
    async def find_by_article_url(
        db_session: AsyncSession,
        article_url: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Find existing records for an article URL."""

        normalized_url = article_url.strip()
        result = await db_session.execute(
            select(SequenceData)
            .where(SequenceData.article_url == normalized_url)
            .order_by(SequenceData.created_at.desc())
            .limit(limit)
        )
        return [DatabaseService.sequence_data_to_dict(record) for record in result.scalars().all()]

    @staticmethod
    async def find_by_gene_or_uniprot(
        db_session: AsyncSession,
        gene: str | None = None,
        protein_uniprot_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Find records by gene name and/or UniProt ID."""

        filters = []
        if gene:
            normalized_gene = gene.strip().lower()
            filters.append(func.lower(SequenceData.gene) == normalized_gene)
        if protein_uniprot_id:
            normalized_uniprot = protein_uniprot_id.strip().lower()
            filters.append(func.lower(SequenceData.protein_uniprot_id) == normalized_uniprot)

        if not filters:
            return []

        result = await db_session.execute(
            select(SequenceData)
            .where(or_(*filters))
            .order_by(SequenceData.created_at.desc())
            .limit(limit)
        )
        return [DatabaseService.sequence_data_to_dict(record) for record in result.scalars().all()]

    @staticmethod
    async def import_csv_to_database(csv_path: str, db_session: AsyncSession) -> bool:
        """Import CSV data into sequence_data."""

        try:
            if not Path(csv_path).exists():
                logger.warning("CSV file not found: %s", csv_path)
                return False

            df = pd.read_csv(csv_path)
            total_records = len(df)
            logger.info("Loading %s records from %s", total_records, csv_path)

            for _, row in df.iterrows():
                try:
                    created_at = datetime.now(timezone.utc)
                    raw_created_at = row.get("created_at", "")
                    if pd.notna(raw_created_at) and raw_created_at:
                        created_at = datetime.fromisoformat(str(raw_created_at))

                    sequence_data = SequenceData(
                        gene=str(row["gene"]) if pd.notna(row.get("gene")) else "",
                        protein_uniprot_id=str(row.get("protein_uniprot_id", ""))
                        if pd.notna(row.get("protein_uniprot_id"))
                        else "",
                        modification_type=str(row.get("modification_type", ""))
                        if pd.notna(row.get("modification_type"))
                        else "",
                        interval=str(row.get("interval", "")) if pd.notna(row.get("interval")) else "",
                        function=str(row.get("function", "")) if pd.notna(row.get("function")) else "",
                        effect=str(row.get("effect", "")) if pd.notna(row.get("effect")) else "",
                        is_longevity_related=_parse_bool(row.get("is_longevity_related", False)),
                        longevity_association=str(row.get("longevity_association", ""))
                        if pd.notna(row.get("longevity_association"))
                        else "",
                        citations=_parse_citations(row.get("citations", "")),
                        article_url=str(row.get("article_url", ""))
                        if pd.notna(row.get("article_url"))
                        else "",
                        created_at=created_at,
                    )
                    db_session.add(sequence_data)
                except Exception:
                    logger.exception("Error preparing CSV row for import")
                    continue

            await db_session.commit()
            logger.info("Successfully imported %s records from %s", total_records, csv_path)
            return True
        except Exception:
            await db_session.rollback()
            logger.exception("Error importing CSV %s", csv_path)
            return False

    @staticmethod
    async def export_to_csv(csv_path: str, db_session: AsyncSession) -> bool:
        """Export sequence_data table to CSV."""

        try:
            sequence_data = await DatabaseService.get_all_sequence_data(db_session, limit=10000)
            if not sequence_data:
                logger.info("No data to export")
                return True

            rows = [DatabaseService.sequence_data_to_dict(record) for record in sequence_data]
            for row in rows:
                row["citations"] = json.dumps(row["citations"]) if row["citations"] else ""

            df = pd.DataFrame(rows)
            df.to_csv(csv_path, index=False)
            logger.info("Exported %s records to %s", len(rows), csv_path)
            return True
        except Exception:
            logger.exception("Error exporting to CSV")
            return False

    @staticmethod
    async def initialize_csv_data() -> None:
        """
        Initialize CSV file and seed database on startup.

        Existing database rows are preserved. CSV import only happens when the database is empty.
        """

        if not os.path.exists(CSV_FILE_PATH):
            os.makedirs(os.path.dirname(CSV_FILE_PATH), exist_ok=True)
            with open(CSV_FILE_PATH, "w") as file:
                file.write(",".join(CSV_HEADERS) + "\n")
            logger.info("Created empty CSV file at %s", CSV_FILE_PATH)

        async for db_session in get_db():
            result = await db_session.execute(text("SELECT COUNT(*) FROM sequence_data"))
            count = result.scalar() or 0
            logger.info("Database has %s existing records", count)

            if count == 0:
                logger.info("Database is empty, importing from CSV")
                success = await DatabaseService.import_csv_to_database(CSV_FILE_PATH, db_session)
                if success:
                    logger.info("Successfully loaded CSV data from %s", CSV_FILE_PATH)
                else:
                    logger.warning("Failed to load CSV data from %s", CSV_FILE_PATH)
            else:
                logger.info("Database already has data, skipping CSV import")
            break
