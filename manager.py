import uuid
import logging
import asyncio
from typing import AsyncGenerator
from agents import SQLiteSession
from agents.items import TResponseInputItem
from configs.endpoints_base_models import AppState, StfRequest
from configs.config import TaskModelConfig
from stf_agents.agents import (
    create_stf_manager_agent,
    create_article_parsing_agent,
    create_data_retrieval_agent,
    create_article_writing_agent,
    create_vision_agent,
)
from runner.stream import run_agent_stream
from utils.create_config import create_stf_run_config
from utils.sse import json_event
from utils.sqlite_utils import get_db_path
from utils.app_context import set_app_state_context


logger = logging.getLogger(__name__)


async def run_stf_agent_stream(
    request: StfRequest,
    app_state: AppState,
    session_id: str
) -> AsyncGenerator[str, None]:
    session_id = session_id or f"session_{uuid.uuid4().hex}"
    event_queue: asyncio.Queue = asyncio.Queue()
    
    yield json_event("start", {"status": "started", "session_id": session_id})

    async def process_stf_agent():
        """Run STF agent and put events in queue"""
        try:
            # Set app state context for tools to access embedding service
            set_app_state_context(app_state)

            logger.debug(
                "Starting STF agent - session_id: %s, model: %s",
                session_id, request.stf_model.model_name
            )

            # SQLite operations: Create session for conversation history storage
            stf_session = SQLiteSession(db_path=get_db_path("sessions.db"), session_id=session_id)

            logger.debug(
                "Session STF initialized - session_id: %s, model: %s",
                session_id, request.stf_model.model_name
            )

            # Check if session has existing history
            existing_items = await stf_session.get_items()
            if existing_items:
                logger.warning(
                    "Resuming session with %d existing items - this may cause errors if switching models - session_id: %s, model: %s",
                    len(existing_items), session_id, request.stf_model.model_name
                )        

            stf_model_config: TaskModelConfig = {
                "model_name": request.stf_model.model_name,
                "model_settings": request.stf_model.model_settings,
            }

            # Create run config with proper settings
            run_config = create_stf_run_config(
                openai_client=app_state.openai_client,
                session_id=session_id,
                stf_model_config=stf_model_config,
            )

            logger.debug(
                "Run config created - session_id: %s, model: %s",
                session_id, request.stf_model.model_name
            )

            # Create specialized agents
            article_parsing_agent = create_article_parsing_agent(run_config)
            data_retrieval_agent = create_data_retrieval_agent(run_config)
            article_writing_agent = create_article_writing_agent(run_config, data_retrieval_agent)
            vision_agent = create_vision_agent(run_config)

            # Create manager agent with handoffs
            agent = create_stf_manager_agent(
                run_config,
                article_parsing_agent,
                data_retrieval_agent,
                article_writing_agent,
                vision_agent
            )

            logger.debug(
                "Agent created - session_id: %s, model: %s",
                session_id, request.stf_model.model_name
            )

            initial_input: list[TResponseInputItem] = [
                {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": request.user_message,
                        },
                    ],
                }
            ]

            async for _ in run_agent_stream(
                agent=agent,
                initial_input=initial_input,
                sql_session=stf_session,
                run_config=run_config,
                session_id=session_id,
                event_queue=event_queue,
            ):
                # Events are put directly in the queue, so we just consume the empty iterator
                pass

            await event_queue.put(("done", {}))
            
        except Exception as e:
            error_msg = str(e)
            logger.error("Run STF agent stream error - session_id: %s, error: %s", session_id, error_msg)
            await event_queue.put(("error", {"message": error_msg}))
            await event_queue.put(("done", {}))

    process_task = asyncio.create_task(process_stf_agent())

    while True:
        event_type, event_data = await event_queue.get()

        # include session_id in each event payload
        payload = {"session_id": session_id, **(event_data or {})}
        yield json_event(event_type, payload)
        
        if event_type == "done":
            break

    await process_task