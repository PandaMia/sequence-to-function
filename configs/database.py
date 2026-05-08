import os
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker


Base = declarative_base()


class SequenceData(Base):
    __tablename__ = "sequence_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gene = Column(String(100), nullable=False, index=True)
    protein_uniprot_id = Column(String(20), index=True)
    modification_type = Column(String(100))
    interval = Column(String(100))
    function = Column(Text)
    effect = Column(Text)
    is_longevity_related = Column(Boolean, default=False, index=True)
    longevity_association = Column(Text)
    citations = Column(JSON)
    article_url = Column(Text, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


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
        await conn.run_sync(Base.metadata.create_all)
