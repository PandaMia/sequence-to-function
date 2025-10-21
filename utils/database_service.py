import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
import pandas as pd
from configs.database import SequenceData, get_db
from configs.config import CSV_FILE_PATH, CSV_HEADERS
from utils.embeddings import create_search_text
from utils.app_context import get_embedding_service


logger = logging.getLogger(__name__)


class DatabaseService:
    
    @staticmethod
    async def save_sequence_data(
        gene: str,
        protein_uniprot_id: str,
        interval: str,
        function: str,
        modification_type: str,
        effect: str,
        longevity_association: str,
        citations: list,
        article_url: str,
        extracted_at: datetime,
        db_session: AsyncSession,
        export_to_csv: bool = True
    ) -> int:
        """Save sequence data to PostgreSQL with automatic embedding generation"""
        try:
            # Generate embedding for semantic search
            embedding = None
            embedding_service = get_embedding_service()
            if embedding_service:
                search_text = create_search_text(gene, function, effect, longevity_association)
                if search_text:
                    logger.info(f"📝 Generating embedding for gene: {gene}")
                    logger.info(f"Search text: {search_text[:100]}...")
                    embedding = await embedding_service.generate_embedding(search_text)
                    if embedding:
                        logger.info(f"✅ Embedding created! Dimensions: {len(embedding)}")
                        logger.info(f"✅ Generated embedding for gene {gene} ({len(embedding)} dimensions)")
                    else:
                        logger.info(f"❌ Failed to generate embedding for gene {gene}")
                        logger.warning(f"Failed to generate embedding for gene {gene}")
                else:
                    logger.info(f"⚠️  No search text for gene {gene}, skipping embedding")
            else:
                logger.info(f"⚠️  Embedding service not available, skipping embedding for {gene}")
                logger.warning("Embedding service not initialized")

            sequence_data = SequenceData(
                gene=gene,
                protein_uniprot_id=protein_uniprot_id,
                interval=interval,
                function=function,
                modification_type=modification_type,
                effect=effect,
                longevity_association=longevity_association,
                citations=citations,
                article_url=article_url,
                extracted_at=extracted_at,
                created_at=datetime.now(timezone.utc),
                embedding=embedding
            )

            db_session.add(sequence_data)
            await db_session.commit()
            await db_session.refresh(sequence_data)

            # Auto-export to CSV after saving (if enabled)
            if export_to_csv:
                await DatabaseService.export_to_csv(CSV_FILE_PATH, db_session)

            logger.info(f"Saved sequence data with ID {sequence_data.id} for gene {gene}")
            return sequence_data.id

        except Exception as e:
            await db_session.rollback()
            logger.error(f"Error saving sequence data for gene {gene}: {str(e)}")
            raise
    
    @staticmethod
    async def get_all_sequence_data(
        db_session: AsyncSession,
        limit: int = 100,
        offset: int = 0
    ) -> List[SequenceData]:
        """Get all sequence data records with pagination"""
        try:
            result = await db_session.execute(
                select(SequenceData)
                .order_by(SequenceData.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error retrieving sequence data: {str(e)}")
            return []
    
    @staticmethod
    async def import_csv_to_database(csv_path: str, db_session: AsyncSession) -> bool:
        """Import CSV data into sequence_data table"""
        try:
            if not Path(csv_path).exists():
                logger.warning(f"CSV file not found: {csv_path}")
                return False
            
            df = pd.read_csv(csv_path)
            logger.info(f"Loading {len(df)} records from {csv_path}")
            
            for _, row in df.iterrows():
                try:
                    citations = json.loads(row['citations']) if pd.notna(row['citations']) and row['citations'] else []
                    
                    extracted_at = datetime.fromisoformat(row['extracted_at']) if pd.notna(row['extracted_at']) and row['extracted_at'] else None
                    
                    await DatabaseService.save_sequence_data(
                        gene=str(row['gene']) if pd.notna(row['gene']) else '',
                        protein_uniprot_id=str(row.get('protein_uniprot_id', '')) if pd.notna(row.get('protein_uniprot_id')) else '',
                        interval=str(row.get('interval', '')) if pd.notna(row.get('interval')) else '',
                        function=str(row.get('function', '')) if pd.notna(row.get('function')) else '',
                        modification_type=str(row.get('modification_type', '')) if pd.notna(row.get('modification_type')) else '',
                        effect=str(row.get('effect', '')) if pd.notna(row.get('effect')) else '',
                        longevity_association=str(row.get('longevity_association', '')) if pd.notna(row.get('longevity_association')) else '',
                        citations=citations,
                        article_url=str(row.get('article_url', '')) if pd.notna(row.get('article_url')) else '',
                        extracted_at=extracted_at,
                        db_session=db_session,
                        export_to_csv=False  # Don't export to CSV when importing from CSV
                    )
                    
                except Exception as e:
                    logger.error(f"Error processing row {row.get('gene', 'unknown')}: {str(e)}")
                    continue
            return True
            
        except Exception as e:
            logger.error(f"Error importing CSV {csv_path}: {str(e)}")
            return False
    
    @staticmethod
    async def export_to_csv(csv_path: str, db_session: AsyncSession) -> bool:
        """Export sequence_data table to CSV"""
        try:
            sequence_data = await DatabaseService.get_all_sequence_data(db_session, limit=10000)
            
            if not sequence_data:
                logger.info("No data to export")
                return True
            
            data = []
            for record in sequence_data:
                data.append({
                    'id': record.id,
                    'gene': record.gene,
                    'protein_uniprot_id': record.protein_uniprot_id,
                    'interval': record.interval,
                    'function': record.function,
                    'modification_type': record.modification_type,
                    'effect': record.effect,
                    'longevity_association': record.longevity_association,
                    'citations': json.dumps(record.citations) if record.citations else '',
                    'article_url': record.article_url,
                    'extracted_at': record.extracted_at.isoformat() if record.extracted_at else '',
                    'created_at': record.created_at.isoformat(),
                    'updated_at': record.updated_at.isoformat()
                })
            
            df = pd.DataFrame(data)
            df.to_csv(csv_path, index=False)
            logger.info(f"Exported {len(data)} records to {csv_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting to CSV: {str(e)}")
            return False
    
    @staticmethod
    async def initialize_csv_data():
        """
        Initialize CSV file and check database on startup.

        IMPORTANT: Does NOT clear existing database data.
        Only creates CSV file if missing and checks record count.
        """

        # Create empty CSV file with headers if it doesn't exist
        if not os.path.exists(CSV_FILE_PATH):
            os.makedirs(os.path.dirname(CSV_FILE_PATH), exist_ok=True)
            with open(CSV_FILE_PATH, 'w') as f:
                f.write(",".join(CSV_HEADERS) + "\n")
            logger.info(f"Created empty CSV file at {CSV_FILE_PATH}")

        # Check database status
        async for db_session in get_db():
            # Count existing records
            result = await db_session.execute(text("SELECT COUNT(*) FROM sequence_data"))
            count = result.scalar()

            logger.info(f"Database has {count} existing records")

            # Only import CSV if database is empty
            if count == 0:
                logger.info("Database is empty, importing from CSV...")
                success = await DatabaseService.import_csv_to_database(CSV_FILE_PATH, db_session)
                if success:
                    logger.info(f"Successfully loaded CSV data from {CSV_FILE_PATH}")
                else:
                    logger.warning(f"Failed to load CSV data from {CSV_FILE_PATH}")
            else:
                logger.info("Database already has data, skipping CSV import")

                # Check for records without embeddings
                result = await db_session.execute(
                    text("SELECT COUNT(*) FROM sequence_data WHERE embedding IS NULL")
                )
                missing_embeddings = result.scalar()

                if missing_embeddings > 0:
                    logger.info(
                        f"Found {missing_embeddings} records without embeddings. "
                        "Generating embeddings automatically..."
                    )
                    generated = await DatabaseService.generate_missing_embeddings(db_session)
                    logger.info(f"Successfully generated {generated} embeddings")
                else:
                    logger.info("All records have embeddings")

            break

    @staticmethod
    async def generate_missing_embeddings(db_session):
        """
        Generate embeddings for all records that don't have them.

        This is useful when:
        - Database was created before embeddings were implemented
        - CSV import happened without embedding service
        - Some records failed to generate embeddings

        Args:
            db_session: AsyncSession - database session to use
        """
        from utils.app_context import get_embedding_service

        embedding_service = get_embedding_service()
        if not embedding_service:
            logger.error("Embedding service not available")
            return 0

        # Find records without embeddings
        result = await db_session.execute(
            select(SequenceData).where(SequenceData.embedding.is_(None))
        )
        records = result.scalars().all()

        if not records:
            logger.info("No records found without embeddings")
            return 0

        logger.info(f"Generating embeddings for {len(records)} records...")
        generated = 0

        for record in records:
            try:
                search_text = create_search_text(
                    record.gene,
                    record.function,
                    record.effect,
                    record.longevity_association
                )

                if search_text:
                    embedding = await embedding_service.generate_embedding(search_text)
                    if embedding:
                        record.embedding = embedding
                        generated += 1
                        logger.debug(f"Generated embedding for gene {record.gene} (ID: {record.id})")
                    else:
                        logger.warning(f"Failed to generate embedding for gene {record.gene} (ID: {record.id})")
                else:
                    logger.warning(f"No search text for gene {record.gene} (ID: {record.id})")

            except Exception as e:
                logger.error(f"Error generating embedding for record {record.id}: {str(e)}")

        # Commit all changes
        await db_session.commit()
        logger.info(f"Successfully generated {generated} embeddings out of {len(records)} records")
        return generated