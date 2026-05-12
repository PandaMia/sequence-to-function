import os
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker


Base = declarative_base()


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(Text, nullable=False, unique=True, index=True)
    full_text = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    sequence_records = relationship("SequenceData", back_populates="article")


class SequenceData(Base):
    __tablename__ = "sequence_data"
    __table_args__ = (
        UniqueConstraint(
            "article_id",
            "gene",
            "protein_uniprot_id",
            "modification_type",
            "interval",
            name="uq_sequence_data_article_gene_modification",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    gene = Column(String(100), nullable=False, index=True)
    protein_uniprot_id = Column(String(20), index=True)
    modification_type = Column(String(100))
    interval = Column(String(100))
    function = Column(Text)
    effect = Column(Text)
    is_longevity_related = Column(Boolean, default=False, index=True)
    longevity_association = Column(Text)
    citations = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    article = relationship("Article", back_populates="sequence_records")


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///databases/sequence_function.db")

if DATABASE_URL.startswith("sqlite"):
    db_path = DATABASE_URL.removeprefix("sqlite+aiosqlite:///")
    if db_path and db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def create_tables() -> None:
    async with engine.begin() as conn:
        if DATABASE_URL.startswith("sqlite"):
            result = await conn.execute(sql_text("PRAGMA table_info(sequence_data)"))
            columns = {row[1] for row in result.fetchall()}
            if columns and "article_id" not in columns:
                suffix = int(datetime.now(timezone.utc).timestamp())
                await conn.execute(sql_text(f"ALTER TABLE sequence_data RENAME TO sequence_data_legacy_{suffix}"))
        await conn.run_sync(Base.metadata.create_all)
