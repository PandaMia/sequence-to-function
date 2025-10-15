import uuid
import json
import logging
from typing import AsyncIterator
from agents import SQLiteSession
from agents.items import TResponseInputItem
from configs.endpoints_base_models import AppState, StfRequest
from configs.config import TaskModelConfig
from stf_agents.agents import create_stf_agent
from runner.stream import run_agent_stream
from utils.create_config import create_stf_run_config


logger = logging.getLogger(__name__)


async def run_stf_agent_stream(
    request: StfRequest,
    app_state: AppState,
) -> AsyncIterator[str]:
    session_id = request.session_id or f"session_{uuid.uuid4().hex}"

    try:
        yield f"data: {json.dumps({'type': 'session_created', 'session_id': session_id})}\n\n"

        logger.debug(
            "Starting STF agent",
            {"session_id": session_id, "model": request.stf_model.model_name},
        )

        stf_session = SQLiteSession(session_id)

        logger.debug(
            "Session STF initialized",
            {"session_id": session_id, "model": request.stf_model.model_name},
        )

        # Check if session has existing history
        existing_items = await stf_session.get_items()
        if existing_items:
            logger.warning(
                f"Resuming session with {len(existing_items)} existing items - this may cause errors if switching models",
                {
                    "session_id": session_id,
                    "item_count": len(existing_items),
                    "model": request.stf_model.model_name,
                },
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
            "Run config created",
            {"session_id": session_id, "model": request.stf_model.model_name},
        )

        agent = create_stf_agent(run_config)

        logger.debug(
            "Agent created",
            {"session_id": session_id, "model": request.stf_model.model_name},
        )

        # Type: ignore needed because TypedDict structure is complex
        initial_input: list[TResponseInputItem] = [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"Analyze the following article to extract sequence-to-function relationships. Link: {request.article_link}",
                    },
                ],
            }
        ]

        # Use simplified runner
        async for event in run_agent_stream(
            agent=agent,
            initial_input=initial_input,
            sql_session=stf_session,
            run_config=run_config,
            session_id=session_id,
        ):
            yield event

    except Exception as e:
        error_msg = str(e)
        logger.error("Run STF agent stream error", {"session_id": session_id, "error": error_msg})

        yield f"data: {json.dumps({
            'type': 'error',
            'message': error_msg,
        })}\n\n"