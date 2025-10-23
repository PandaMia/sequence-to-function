"""Business logic for STF agent execution."""

import uuid
import json
import logging
from typing import AsyncGenerator

from agents import SQLiteSession
from agents.items import TResponseInputItem

from app_startup.state import AppState
from api.stf.schemas import StfRequest
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
    """
    Execute the STF agent with streaming output.

    Args:
        request: STF request with user message and model config
        app_state: Application state with clients and services
        session_id: Session ID for conversation tracking

    Yields:
        SSE formatted events with agent execution progress
    """
    session_id = session_id or f"session_{uuid.uuid4().hex}"

    yield json_event("start", {"status": "started", "session_id": session_id})

    try:
        # Set app state context for tools to access embedding service
        set_app_state_context(app_state)

        logger.debug(
            f"Starting STF agent - session_id: {session_id}, model: {request.stf_model.model_name}"
        )

        # SQLite operations: Create session for conversation history storage
        stf_session = SQLiteSession(db_path=get_db_path("sessions.db"), session_id=session_id)

        logger.debug(
            f"Session STF initialized - session_id: {session_id}, model: {request.stf_model.model_name}"
        )

        # Check if session has existing history
        existing_items = await stf_session.get_items()
        if existing_items:
            logger.warning(
                f"Resuming session with {len(existing_items)} existing items - this may cause errors if switching models - session_id: {session_id}, model: {request.stf_model.model_name}"
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
            f"Run config created - session_id: {session_id}, model: {request.stf_model.model_name}"
        )

        # Create specialized agents
        article_parsing_agent = create_article_parsing_agent(run_config)
        data_retrieval_agent = create_data_retrieval_agent(run_config)
        article_writing_agent = create_article_writing_agent(run_config)
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
            f"Agent created - session_id: {session_id}, model: {request.stf_model.model_name}"
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

        # Stream events directly without buffering in a queue
        async for event_json in run_agent_stream(
            agent=agent,
            initial_input=initial_input,
            sql_session=stf_session,
            run_config=run_config,
            session_id=session_id,
            event_queue=None,  # No queue - stream directly
        ):
            # Parse the JSON event from run_agent_stream
            event_data = json.loads(event_json)
            event_type = event_data.get('type', 'unknown')

            # Include session_id in each event payload
            payload = {"session_id": session_id, **event_data}
            yield json_event(event_type, payload)

        # Send done event
        yield json_event("done", {"session_id": session_id})

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Run STF agent stream error - session_id: {session_id}, error: {error_msg}")
        yield json_event("error", {"session_id": session_id, "message": error_msg})
        yield json_event("done", {"session_id": session_id})
