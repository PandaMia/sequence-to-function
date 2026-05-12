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

from configs.config import ARTICLE_CSV_FILE_PATH, ARTICLE_CSV_HEADERS, CSV_FILE_PATH, CSV_HEADERS
from configs.database import Article, SequenceData, get_db


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


def _parse_optional_int(value: Any) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
        return None
    try:
        return int(value)
    except Exception:
        return None


def _parse_datetime(value: Any) -> datetime:
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return datetime.now(timezone.utc)


class DatabaseService:
    @staticmethod
    def sequence_data_to_dict(record: SequenceData, article: Article | None = None) -> dict[str, Any]:
        return {
            "id": record.id,
            "article_id": record.article_id,
            "gene": record.gene,
            "protein_uniprot_id": record.protein_uniprot_id,
            "modification_type": record.modification_type,
            "interval": record.interval,
            "function": record.function,
            "effect": record.effect,
            "is_longevity_related": record.is_longevity_related,
            "longevity_association": record.longevity_association,
            "citations": record.citations or [],
            "article_url": article.url if article else "",
            "article_text": article.full_text if article and article.full_text else "",
            "created_at": record.created_at.isoformat() if record.created_at else None,
        }

    @staticmethod
    def sequence_data_to_csv_dict(record: SequenceData) -> dict[str, Any]:
        return {
            "id": record.id,
            "article_id": record.article_id,
            "gene": record.gene,
            "protein_uniprot_id": record.protein_uniprot_id,
            "modification_type": record.modification_type,
            "interval": record.interval,
            "function": record.function,
            "effect": record.effect,
            "is_longevity_related": record.is_longevity_related,
            "longevity_association": record.longevity_association,
            "citations": json.dumps(record.citations or []) if record.citations else "",
            "created_at": record.created_at.isoformat() if record.created_at else None,
        }

    @staticmethod
    def article_to_csv_dict(article: Article) -> dict[str, Any]:
        return {
            "id": article.id,
            "url": article.url,
            "article_text": article.full_text or "",
            "created_at": article.created_at.isoformat() if article.created_at else None,
            "updated_at": article.updated_at.isoformat() if article.updated_at else None,
        }

    @staticmethod
    async def get_or_create_article(
        db_session: AsyncSession,
        article_url: str,
        article_text: str = "",
        article_id: int | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> Article:
        normalized_url = article_url.strip()
        now = datetime.now(timezone.utc)

        if normalized_url:
            result = await db_session.execute(select(Article).where(Article.url == normalized_url))
            article = result.scalar_one_or_none()
            if article is not None:
                if article_text and (not article.full_text or len(article_text) > len(article.full_text)):
                    article.full_text = article_text
                    article.updated_at = updated_at or now
                    await db_session.flush()
                return article

        if article_id is not None:
            article = await db_session.get(Article, article_id)
            if article is not None:
                if normalized_url and article.url != normalized_url:
                    article.url = normalized_url
                if article_text and (not article.full_text or len(article_text) > len(article.full_text)):
                    article.full_text = article_text
                article.updated_at = updated_at or article.updated_at or now
                await db_session.flush()
                return article

        article = Article(
            id=article_id,
            url=normalized_url,
            full_text=article_text or "",
            created_at=created_at or now,
            updated_at=updated_at or now,
        )
        db_session.add(article)
        await db_session.flush()
        return article

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
        article_text: str = "",
        export_to_csv: bool = True,
    ) -> int:
        """Save sequence data to the database."""

        try:
            article = await DatabaseService.get_or_create_article(
                db_session=db_session,
                article_url=article_url,
                article_text=article_text,
            )
            result = await db_session.execute(
                select(SequenceData).where(
                    SequenceData.article_id == article.id,
                    SequenceData.gene == gene,
                    SequenceData.protein_uniprot_id == protein_uniprot_id,
                    SequenceData.modification_type == modification_type,
                    SequenceData.interval == interval,
                )
            )
            existing = result.scalar_one_or_none()
            if existing is not None:
                existing.function = function
                existing.effect = effect
                existing.is_longevity_related = is_longevity_related
                existing.longevity_association = longevity_association
                existing.citations = citations
                await db_session.commit()

                if export_to_csv:
                    await DatabaseService.export_to_csv(CSV_FILE_PATH, db_session)

                logger.info("Updated existing sequence data ID %s for gene %s", existing.id, gene)
                return existing.id

            sequence_data = SequenceData(
                article_id=article.id,
                gene=gene,
                protein_uniprot_id=protein_uniprot_id,
                modification_type=modification_type,
                interval=interval,
                function=function,
                effect=effect,
                is_longevity_related=is_longevity_related,
                longevity_association=longevity_association,
                citations=citations,
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
    ) -> list[tuple[SequenceData, Article]]:
        """Get all sequence data records with pagination."""

        try:
            result = await db_session.execute(
                select(SequenceData, Article)
                .join(Article, SequenceData.article_id == Article.id)
                .order_by(SequenceData.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            return list(result.all())
        except Exception:
            logger.exception("Error retrieving sequence data")
            return []

    @staticmethod
    async def get_all_articles(db_session: AsyncSession) -> list[Article]:
        """Get all articles sorted by ID."""

        try:
            result = await db_session.execute(select(Article).order_by(Article.id.asc()))
            return list(result.scalars().all())
        except Exception:
            logger.exception("Error retrieving articles")
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
            select(SequenceData, Article)
            .join(Article, SequenceData.article_id == Article.id)
            .where(Article.url == normalized_url)
            .order_by(SequenceData.created_at.desc())
            .limit(limit)
        )
        return [DatabaseService.sequence_data_to_dict(record, article) for record, article in result.all()]

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
            select(SequenceData, Article)
            .join(Article, SequenceData.article_id == Article.id)
            .where(or_(*filters))
            .order_by(SequenceData.created_at.desc())
            .limit(limit)
        )
        return [DatabaseService.sequence_data_to_dict(record, article) for record, article in result.all()]

    @staticmethod
    async def _csv_record_exists(
        db_session: AsyncSession,
        record_id: int | None,
        article_id: int,
        gene: str,
        protein_uniprot_id: str,
        modification_type: str,
        interval: str,
    ) -> bool:
        if record_id is not None:
            existing = await db_session.get(SequenceData, record_id)
            if existing is not None:
                return True

        result = await db_session.execute(
            select(SequenceData.id).where(
                SequenceData.article_id == article_id,
                SequenceData.gene == gene,
                SequenceData.protein_uniprot_id == protein_uniprot_id,
                SequenceData.modification_type == modification_type,
                SequenceData.interval == interval,
            )
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def import_articles_csv(article_csv_path: str, db_session: AsyncSession) -> dict[int, Article]:
        """Import missing article rows from articles.csv without duplicating URLs."""

        articles_by_csv_id: dict[int, Article] = {}
        if not Path(article_csv_path).exists():
            logger.info("Article CSV file not found: %s", article_csv_path)
            return articles_by_csv_id

        df = pd.read_csv(article_csv_path)
        logger.info("Loading %s articles from %s", len(df), article_csv_path)
        for _, row in df.iterrows():
            try:
                article_id = _parse_optional_int(row.get("id"))
                article_url = str(row.get("url", "")) if pd.notna(row.get("url")) else ""
                if not article_url.strip():
                    continue
                article_text = (
                    str(row.get("article_text", ""))
                    if "article_text" in row and pd.notna(row.get("article_text"))
                    else ""
                )
                article = await DatabaseService.get_or_create_article(
                    db_session=db_session,
                    article_url=article_url,
                    article_text=article_text,
                    article_id=article_id,
                    created_at=_parse_datetime(row.get("created_at")),
                    updated_at=_parse_datetime(row.get("updated_at")),
                )
                if article_id is not None:
                    articles_by_csv_id[article_id] = article
            except Exception:
                logger.exception("Error preparing article CSV row for import")
                continue

        return articles_by_csv_id

    @staticmethod
    async def import_csv_to_database(
        csv_path: str,
        db_session: AsyncSession,
        article_csv_path: str | None = None,
    ) -> bool:
        """Import missing CSV rows into sequence_data without duplicating existing records."""

        try:
            article_csv_path = article_csv_path or ARTICLE_CSV_FILE_PATH
            if not Path(csv_path).exists():
                logger.warning("CSV file not found: %s", csv_path)
                return False

            articles_by_csv_id = await DatabaseService.import_articles_csv(article_csv_path, db_session)
            df = pd.read_csv(csv_path)
            total_records = len(df)
            logger.info("Loading %s records from %s", total_records, csv_path)

            imported = 0
            skipped = 0
            for _, row in df.iterrows():
                try:
                    record_id = _parse_optional_int(row.get("id"))
                    created_at = _parse_datetime(row.get("created_at"))

                    gene = str(row["gene"]) if pd.notna(row.get("gene")) else ""
                    protein_uniprot_id = (
                        str(row.get("protein_uniprot_id", ""))
                        if pd.notna(row.get("protein_uniprot_id"))
                        else ""
                    )
                    modification_type = (
                        str(row.get("modification_type", ""))
                        if pd.notna(row.get("modification_type"))
                        else ""
                    )
                    interval = str(row.get("interval", "")) if pd.notna(row.get("interval")) else ""
                    article_id = _parse_optional_int(row.get("article_id"))
                    article = articles_by_csv_id.get(article_id) if article_id is not None else None
                    if article is None and article_id is not None:
                        article = await db_session.get(Article, article_id)

                    if article is None:
                        article_url = (
                            str(row.get("article_url", ""))
                            if "article_url" in row and pd.notna(row.get("article_url"))
                            else ""
                        )
                        article_text = (
                            str(row.get("article_text", ""))
                            if "article_text" in row and pd.notna(row.get("article_text"))
                            else ""
                        )
                        if not article_url.strip():
                            logger.warning("Skipping CSV row without article_id or article_url: id=%s", record_id)
                            skipped += 1
                            continue
                        article = await DatabaseService.get_or_create_article(
                            db_session=db_session,
                            article_url=article_url,
                            article_text=article_text,
                        )

                    if await DatabaseService._csv_record_exists(
                        db_session=db_session,
                        record_id=record_id,
                        article_id=article.id,
                        gene=gene,
                        protein_uniprot_id=protein_uniprot_id,
                        modification_type=modification_type,
                        interval=interval,
                    ):
                        skipped += 1
                        continue

                    sequence_data = SequenceData(
                        id=record_id,
                        article_id=article.id,
                        gene=gene,
                        protein_uniprot_id=protein_uniprot_id,
                        modification_type=modification_type,
                        interval=interval,
                        function=str(row.get("function", "")) if pd.notna(row.get("function")) else "",
                        effect=str(row.get("effect", "")) if pd.notna(row.get("effect")) else "",
                        is_longevity_related=_parse_bool(row.get("is_longevity_related", False)),
                        longevity_association=str(row.get("longevity_association", ""))
                        if pd.notna(row.get("longevity_association"))
                        else "",
                        citations=_parse_citations(row.get("citations", "")),
                        created_at=created_at,
                    )
                    db_session.add(sequence_data)
                    imported += 1
                except Exception:
                    logger.exception("Error preparing CSV row for import")
                    continue

            await db_session.commit()
            logger.info(
                "CSV sync completed from %s: imported=%s, skipped_existing=%s, total=%s",
                csv_path,
                imported,
                skipped,
                total_records,
            )
            return True
        except Exception:
            await db_session.rollback()
            logger.exception("Error importing CSV %s", csv_path)
            return False

    @staticmethod
    async def export_to_csv(
        csv_path: str,
        db_session: AsyncSession,
        article_csv_path: str | None = None,
    ) -> bool:
        """Export articles and sequence_data tables to CSV."""

        try:
            article_csv_path = article_csv_path or ARTICLE_CSV_FILE_PATH
            Path(csv_path).parent.mkdir(parents=True, exist_ok=True)
            Path(article_csv_path).parent.mkdir(parents=True, exist_ok=True)

            articles = await DatabaseService.get_all_articles(db_session)
            article_rows = [DatabaseService.article_to_csv_dict(article) for article in articles]
            pd.DataFrame(article_rows, columns=ARTICLE_CSV_HEADERS).to_csv(article_csv_path, index=False)
            logger.info("Exported %s articles to %s", len(article_rows), article_csv_path)

            sequence_data = await DatabaseService.get_all_sequence_data(db_session, limit=10000)
            if not sequence_data:
                logger.info("No data to export")
                return True

            rows = [DatabaseService.sequence_data_to_csv_dict(record) for record, _article in sequence_data]

            rows.sort(key=lambda item: int(item["id"] or 0))
            df = pd.DataFrame(rows, columns=CSV_HEADERS)
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

        Existing database rows are preserved. Missing CSV rows are imported on every startup.
        """

        if not os.path.exists(CSV_FILE_PATH):
            os.makedirs(os.path.dirname(CSV_FILE_PATH), exist_ok=True)
            with open(CSV_FILE_PATH, "w") as file:
                file.write(",".join(CSV_HEADERS) + "\n")
            logger.info("Created empty CSV file at %s", CSV_FILE_PATH)

        if not os.path.exists(ARTICLE_CSV_FILE_PATH):
            os.makedirs(os.path.dirname(ARTICLE_CSV_FILE_PATH), exist_ok=True)
            with open(ARTICLE_CSV_FILE_PATH, "w") as file:
                file.write(",".join(ARTICLE_CSV_HEADERS) + "\n")
            logger.info("Created empty article CSV file at %s", ARTICLE_CSV_FILE_PATH)

        async for db_session in get_db():
            result = await db_session.execute(text("SELECT COUNT(*) FROM sequence_data"))
            count = result.scalar() or 0
            logger.info("Database has %s existing records", count)

            success = await DatabaseService.import_csv_to_database(CSV_FILE_PATH, db_session)
            if success:
                logger.info("Synchronized database from %s", CSV_FILE_PATH)
                await DatabaseService.export_to_csv(CSV_FILE_PATH, db_session)
            else:
                logger.warning("Failed to synchronize database from %s", CSV_FILE_PATH)
            break
