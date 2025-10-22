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
                modification_type=modification_type,
                interval=interval,
                function=function,
                effect=effect,
                is_longevity_related=is_longevity_related,
                longevity_association=longevity_association,
                citations=citations,
                article_url=article_url,
                created_at=created_at,
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
    async def import_csv_to_database(csv_path: str, db_session: AsyncSession, batch_size: int = 50) -> bool:
        """
        Import CSV data into sequence_data table with batch embedding generation.

        Args:
            csv_path: Path to CSV file
            db_session: Database session
            batch_size: Number of records to process in each batch for embeddings (default: 50)
        """
        try:
            if not Path(csv_path).exists():
                logger.warning(f"CSV file not found: {csv_path}")
                return False

            df = pd.read_csv(csv_path)
            total_records = len(df)
            logger.info(f"Loading {total_records} records from {csv_path}")

            # Get embedding service
            embedding_service = get_embedding_service()
            if not embedding_service:
                logger.warning("Embedding service not available, importing without embeddings")
                batch_size = 0  # Disable batch processing

            # Process records in batches
            for batch_start in range(0, total_records, max(1, batch_size)):
                batch_end = min(batch_start + batch_size, total_records)
                batch_df = df.iloc[batch_start:batch_end]

                logger.info(f"Processing batch {batch_start}-{batch_end} of {total_records}")

                # Prepare batch data
                batch_records = []
                batch_texts = []

                for _, row in batch_df.iterrows():
                    try:
                        gene = str(row['gene']) if pd.notna(row['gene']) else ''
                        function = str(row.get('function', '')) if pd.notna(row.get('function')) else ''
                        effect = str(row.get('effect', '')) if pd.notna(row.get('effect')) else ''
                        longevity_association = str(row.get('longevity_association', '')) if pd.notna(row.get('longevity_association')) else ''

                        # Create record data
                        record_data = {
                            'gene': gene,
                            'protein_uniprot_id': str(row.get('protein_uniprot_id', '')) if pd.notna(row.get('protein_uniprot_id')) else '',
                            'modification_type': str(row.get('modification_type', '')) if pd.notna(row.get('modification_type')) else '',
                            'interval': str(row.get('interval', '')) if pd.notna(row.get('interval')) else '',
                            'function': function,
                            'effect': effect,
                            'is_longevity_related': bool(row.get('is_longevity_related', False)) if pd.notna(row.get('is_longevity_related')) else False,
                            'longevity_association': longevity_association,
                            'citations': json.loads(row['citations']) if pd.notna(row['citations']) and row['citations'] else [],
                            'article_url': str(row.get('article_url', '')) if pd.notna(row.get('article_url')) else '',
                            'created_at': datetime.fromisoformat(row['created_at']) if pd.notna(row['created_at']) and row['created_at'] else datetime.now(timezone.utc),
                        }

                        batch_records.append(record_data)

                        # Create search text for embedding
                        if embedding_service:
                            search_text = create_search_text(gene, function, effect, longevity_association)
                            batch_texts.append(search_text)

                    except Exception as e:
                        logger.error(f"Error preparing row {row.get('gene', 'unknown')}: {str(e)}")
                        continue

                # Generate embeddings for the batch
                embeddings = []
                if embedding_service and batch_texts:
                    logger.info(f"Generating embeddings for batch of {len(batch_texts)} records")
                    embeddings = await embedding_service.generate_embeddings_batch(batch_texts)
                    logger.info(f"Generated {sum(1 for e in embeddings if e is not None)} embeddings")

                # Save records to database
                for i, record_data in enumerate(batch_records):
                    try:
                        # Add embedding if available
                        embedding = embeddings[i] if i < len(embeddings) else None

                        sequence_data = SequenceData(
                            gene=record_data['gene'],
                            protein_uniprot_id=record_data['protein_uniprot_id'],
                            modification_type=record_data['modification_type'],
                            interval=record_data['interval'],
                            function=record_data['function'],
                            effect=record_data['effect'],
                            is_longevity_related=record_data['is_longevity_related'],
                            longevity_association=record_data['longevity_association'],
                            citations=record_data['citations'],
                            article_url=record_data['article_url'],
                            created_at=record_data['created_at'],
                            embedding=embedding
                        )

                        db_session.add(sequence_data)

                    except Exception as e:
                        logger.error(f"Error saving record {record_data.get('gene', 'unknown')}: {str(e)}")
                        continue

                # Commit batch
                await db_session.commit()
                logger.info(f"Committed batch {batch_start}-{batch_end}")

            logger.info(f"Successfully imported {total_records} records from {csv_path}")
            return True

        except Exception as e:
            await db_session.rollback()
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
                    'modification_type': record.modification_type,
                    'interval': record.interval,
                    'function': record.function,
                    'effect': record.effect,
                    'is_longevity_related': record.is_longevity_related,
                    'longevity_association': record.longevity_association,
                    'citations': json.dumps(record.citations) if record.citations else '',
                    'article_url': record.article_url,
                    'created_at': record.created_at.isoformat() if record.created_at else '',
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
    async def generate_missing_embeddings(db_session, batch_size: int = 50):
        """
        Generate embeddings for all records that don't have them using batch processing.

        This is useful when:
        - Database was created before embeddings were implemented
        - CSV import happened without embedding service
        - Some records failed to generate embeddings

        Args:
            db_session: AsyncSession - database session to use
            batch_size: Number of embeddings to generate in each batch (default: 50)
        """
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

        total_records = len(records)
        logger.info(f"Generating embeddings for {total_records} records using batch processing...")
        generated = 0

        # Process records in batches
        for batch_start in range(0, total_records, batch_size):
            batch_end = min(batch_start + batch_size, total_records)
            batch_records = records[batch_start:batch_end]

            logger.info(f"Processing batch {batch_start}-{batch_end} of {total_records}")

            # Prepare batch texts
            batch_texts = []
            batch_record_map = []  # Map to track which text belongs to which record

            for record in batch_records:
                search_text = create_search_text(
                    record.gene,
                    record.function,
                    record.effect,
                    record.longevity_association
                )

                if search_text:
                    batch_texts.append(search_text)
                    batch_record_map.append(record)
                else:
                    logger.warning(f"No search text for gene {record.gene} (ID: {record.id})")

            # Generate embeddings for the batch
            if batch_texts:
                try:
                    logger.info(f"Generating embeddings for batch of {len(batch_texts)} records")
                    embeddings = await embedding_service.generate_embeddings_batch(batch_texts)

                    # Assign embeddings to records
                    for i, embedding in enumerate(embeddings):
                        if embedding and i < len(batch_record_map):
                            record = batch_record_map[i]
                            record.embedding = embedding
                            generated += 1
                            logger.debug(f"Generated embedding for gene {record.gene} (ID: {record.id})")
                        elif i < len(batch_record_map):
                            record = batch_record_map[i]
                            logger.warning(f"Failed to generate embedding for gene {record.gene} (ID: {record.id})")

                except Exception as e:
                    logger.error(f"Error generating embeddings for batch: {str(e)}")

            # Commit batch changes
            await db_session.commit()
            logger.info(f"Committed batch {batch_start}-{batch_end}, total generated: {generated}")

        logger.info(f"Successfully generated {generated} embeddings out of {total_records} records")
        return generated