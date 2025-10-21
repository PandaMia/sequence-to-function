import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, String, Text, DateTime, Integer, JSON
from datetime import datetime, timezone
from typing import AsyncGenerator


class Base(DeclarativeBase):
    pass


class SequenceData(Base):
    __tablename__ = "sequence_data"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    gene = Column(String(100), nullable=False, index=True)  # Gene name only (e.g., NFE2L2)
    protein_uniprot_id = Column(String(20), index=True)  # UniProt ID (e.g., Q16236)
    # Interval information as separate string fields
    interval = Column(String(100))  # Format: "AA 76–93" (amino acid positions)
    function = Column(Text)  # Function description
    # Modification information as separate string fields
    modification_type = Column(String(100))  # Type of modification (deletion, substitution, etc.)
    effect = Column(Text)  # Effect of the modification
    longevity_association = Column(Text)
    citations = Column(JSON)  # Array of citation strings
    article_url = Column(Text)
    extracted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://postgres:password@localhost:5432/sequence_function_db"
)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
