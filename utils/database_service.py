import json
import logging
from datetime import datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from configs.database import SequenceFunctionExtraction, get_db


logger = logging.getLogger(__name__)


class DatabaseService:
    
    @staticmethod
    async def save_extraction(
        session_id: str,
        article_link: str,
        extraction_data: dict,
        model_name: str,
        db_session: AsyncSession
    ) -> int:
        """Save sequence-to-function extraction data to PostgreSQL"""
        try:
            extraction = SequenceFunctionExtraction(
                session_id=session_id,
                article_link=article_link,
                extraction_data=json.dumps(extraction_data),
                model_name=model_name,
                created_at=datetime.utcnow()
            )
            
            db_session.add(extraction)
            await db_session.commit()
            await db_session.refresh(extraction)
            
            logger.info(f"Saved extraction with ID {extraction.id} for session {session_id}")
            return extraction.id
            
        except Exception as e:
            await db_session.rollback()
            logger.error(f"Error saving extraction for session {session_id}: {str(e)}")
            raise
    
    @staticmethod
    async def get_extraction_by_session(
        session_id: str,
        db_session: AsyncSession
    ) -> Optional[SequenceFunctionExtraction]:
        """Get extraction data by session ID"""
        try:
            result = await db_session.execute(
                select(SequenceFunctionExtraction)
                .where(SequenceFunctionExtraction.session_id == session_id)
                .order_by(SequenceFunctionExtraction.created_at.desc())
            )
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Error retrieving extraction for session {session_id}: {str(e)}")
            return None
    
    @staticmethod
    async def get_all_extractions(
        db_session: AsyncSession,
        limit: int = 100,
        offset: int = 0
    ) -> List[SequenceFunctionExtraction]:
        """Get all extraction records with pagination"""
        try:
            result = await db_session.execute(
                select(SequenceFunctionExtraction)
                .order_by(SequenceFunctionExtraction.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error retrieving extractions: {str(e)}")
            return []
    
    @staticmethod
    async def update_extraction_data(
        extraction_id: int,
        extraction_data: dict,
        db_session: AsyncSession
    ) -> bool:
        """Update extraction data for an existing record"""
        try:
            await db_session.execute(
                update(SequenceFunctionExtraction)
                .where(SequenceFunctionExtraction.id == extraction_id)
                .values(
                    extraction_data=json.dumps(extraction_data),
                    updated_at=datetime.utcnow()
                )
            )
            await db_session.commit()
            
            logger.info(f"Updated extraction data for ID {extraction_id}")
            return True
            
        except Exception as e:
            await db_session.rollback()
            logger.error(f"Error updating extraction {extraction_id}: {str(e)}")
            return False