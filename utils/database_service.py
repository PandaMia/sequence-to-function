import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text
import pandas as pd
from configs.database import SequenceData, get_db
from configs.config import CSV_FILE_PATH, CSV_HEADERS


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
        """Save sequence data to PostgreSQL"""
        try:
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
                created_at=datetime.now(timezone.utc)
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
        """Initialize CSV file and load data into database on startup"""
        
        # Create empty CSV file with headers if it doesn't exist
        if not os.path.exists(CSV_FILE_PATH):
            os.makedirs(os.path.dirname(CSV_FILE_PATH), exist_ok=True)
            with open(CSV_FILE_PATH, 'w') as f:
                f.write(",".join(CSV_HEADERS) + "\n")
            logger.info(f"Created empty CSV file at {CSV_FILE_PATH}")
        
        df = pd.read_csv(CSV_FILE_PATH)
        
        # Clear existing data from database and reload from CSV
        async for db_session in get_db():
            # Clear the table
            await db_session.execute(delete(SequenceData))
            await db_session.execute(text("ALTER SEQUENCE sequence_data_id_seq RESTART WITH 1"))
            await db_session.commit()
            logger.info("Cleared existing sequence_data table and reset ID sequence")
            
            # Load CSV data into database
            success = await DatabaseService.import_csv_to_database(CSV_FILE_PATH, db_session)
            if success:
                logger.info(f"Successfully loaded CSV data from {CSV_FILE_PATH}")
            else:
                logger.warning(f"Failed to load CSV data from {CSV_FILE_PATH}")
            break