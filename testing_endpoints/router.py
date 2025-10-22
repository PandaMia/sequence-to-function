"""
Testing endpoints router for sequence-to-function service
"""

from typing import Callable
from fastapi import APIRouter, Depends
from sqlalchemy import text
from configs.database import get_db   
from configs.endpoints_base_models import AppState


def get_testing_router(app_state_getter: Callable[[], AppState]) -> APIRouter:
    """
    Create testing router with app state dependency
    
    Args:
        app_state_getter: Function to get app state
        
    Returns:
        APIRouter with testing endpoints
    """
    router = APIRouter(prefix="/testing", tags=["testing"])

    @router.get("/sequence-data-count")
    async def get_sequence_data_count(app_state: AppState = Depends(app_state_getter)):
        """
        Get total number of rows in sequence_data table
        
        Returns:
            Total record count
        """
        try:            
            async for db_session in get_db():
                result = await db_session.execute(text("SELECT COUNT(*) FROM sequence_data"))
                total_count = result.scalar()
                
                return {
                    "status": "success",
                    "total_records": total_count
                }
                
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to get record count: {str(e)}"
            }

    @router.get("/delete-sequence-data-table")
    async def delete_sequence_data_table(app_state: AppState = Depends(app_state_getter)):
        """
        Delete the sequence_data table
        
        Returns:
            Result of table deletion
        """
        try:            
            async for db_session in get_db():
                await db_session.execute(text("DROP TABLE IF EXISTS sequence_data CASCADE"))
                await db_session.commit()
                
                return {
                    "status": "success",
                    "message": "sequence_data table deleted successfully"
                }
                
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to delete table: {str(e)}"
            }

    return router