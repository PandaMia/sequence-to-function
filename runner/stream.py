import json
import logging
import asyncio
import os
from typing import Any, AsyncIterator, Optional

from agents import Agent, Runner, RunConfig, SQLiteSession
from agents.items import TResponseInputItem
from pydantic import BaseModel


logger = logging.getLogger(__name__)


def _max_agent_turns() -> int:
    try:
        return int(os.getenv("STF_MAX_AGENT_TURNS", "25"))
    except ValueError:
        return 25


def _final_response_payload(final_obj: Any) -> dict[str, Any] | list[Any]:
    if isinstance(final_obj, BaseModel):
        final_obj = final_obj.model_dump()

    if final_obj is None:
        return {
            "message": "Task execution completed",
            "message_format": "markdown",
        }

    if isinstance(final_obj, str):
        return {
            "message": final_obj,
            "message_format": "markdown",
        }

    if isinstance(final_obj, dict):
        if "message" in final_obj:
            return {
                **final_obj,
                "message": str(final_obj["message"]),
                "message_format": final_obj.get("message_format", "markdown"),
            }
        return final_obj

    if isinstance(final_obj, list):
        return final_obj

    return {
        "message": str(final_obj),
        "message_format": "markdown",
    }


async def run_agent_stream(
    agent: Agent,
    initial_input: list[TResponseInputItem],
    sql_session: SQLiteSession,
    run_config: RunConfig,
    session_id: str,
    event_queue: Optional[asyncio.Queue] = None,
) -> AsyncIterator[str]:
    """
    Run agent with streaming output.

    Args:
        agent: The agent to run
        initial_input: Initial input with user prompt
        sql_session: SQLiteSession session for persistence
        run_config: Run configuration
        session_id: Session ID for tracing
        event_queue: Optional queue to put events into instead of yielding

    Yields:
        SSE events as strings (only if event_queue is None)
    """
    
    try:
        # Single run_streamed call - agent handles everything
        result = Runner.run_streamed(
            agent,
            input=initial_input,
            session=sql_session,
            run_config=run_config,
            max_turns=_max_agent_turns(),
        )

        # Track state for event handling
        tool_call_count = 0

        # Stream events
        async for event in result.stream_events():
            # Handle reasoning deltas
            if event.type == "raw_response_event":
                # Handle reasoning part completion (add newlines between parts)
                if (
                    hasattr(event.data, "type")
                    and event.data.type == "response.reasoning_summary_part.done"
                ):
                    # Send a newline to separate reasoning parts
                    event_data = {
                        'type': 'reasoning_delta',
                        'content': '\n\n',
                    }
                    if event_queue:
                        await event_queue.put(('reasoning_delta', event_data))
                    else:
                        yield json.dumps(event_data)

                # Handle reasoning text deltas
                elif (
                    hasattr(event.data, "type")
                    and event.data.type == "response.reasoning_summary_text.delta"
                ):
                    event_data = {
                        'type': 'reasoning_delta',
                        'content': event.data.delta,
                    }
                    if event_queue:
                        await event_queue.put(('reasoning_delta', event_data))
                    else:
                        yield json.dumps(event_data)

            # Handle run items
            elif event.type == "run_item_stream_event":
                if event.item.type == "reasoning_item":
                    logger.debug(
                        "Reasoning completed - session_id: %s",
                        session_id
                    )

                elif event.item.type == "message_item":
                    # Skip intermediate message items from agents
                    # These are the "I will analyze..." type messages we want to suppress
                    logger.debug(
                        "Skipping intermediate message item - session_id: %s",
                        session_id
                    )
                elif event.item.type == "tool_call_item":
                    tool_name = None
                    tool_args = None

                    if hasattr(event.item, "raw_item"):
                        raw_item = event.item.raw_item
                        # ResponseFunctionToolCall and McpCall have 'name' and 'arguments'
                        if hasattr(raw_item, "name"):
                            tool_name = getattr(raw_item, "name", None)
                        if hasattr(raw_item, "arguments"):
                            tool_args = getattr(raw_item, "arguments", None)
                        # Other types use 'action' or 'code' instead
                        elif hasattr(raw_item, "action"):
                            tool_name = raw_item.type
                            tool_args = getattr(raw_item, "action", None)
                        elif hasattr(raw_item, "code"):
                            tool_name = "code_interpreter"
                            tool_args = getattr(raw_item, "code", None)

                    tool_call_count += 1

                    logger.info(
                        "Tool called - session_id: %s, tool: %s, tool_call_count: %d, args: %s",
                        session_id, tool_name, tool_call_count, tool_args
                    )

                    # Stream tool call to client
                    event_data = {
                        'type': 'tool_call',
                        'tool': tool_name,
                        'arguments': tool_args,
                    }
                    if event_queue:
                        await event_queue.put(('tool_call', event_data))
                    else:
                        yield json.dumps(event_data)

                elif event.item.type == "tool_call_output_item":
                    output = event.item.output

                    logger.debug(
                        "Tool output received - session_id: %s, output_preview: %s, has_visual_feedback: %s",
                        session_id, str(output)[:200], "VISUAL FEEDBACK:" in str(output)
                    )

                    # Stream tool output to client
                    event_data = {
                        'type': 'tool_output',
                        'content': str(output),
                    }
                    if event_queue:
                        await event_queue.put(('tool_output', event_data))
                    else:
                        yield json.dumps(event_data)

        # Agent completed - final_output is the response
        logger.info(
            "Agent run completed - session_id: %s, tool_calls: %d",
            session_id, tool_call_count
        )

        # Extract final output from agent
        #final_output_text = str(result.final_output) if result.final_output else ""
        final_obj = result.final_output

        # Send final response (agent's natural completion)
        

        final_payload = _final_response_payload(final_obj)

        event_data = {
            'type': 'final_response',
            'content': final_payload,
        }
        if event_queue:
            await event_queue.put(('final_response', event_data))
        else:
            yield json.dumps(event_data)

        event_data = {
            'type': 'completed',
            'tool_calls': tool_call_count,
        }
        if event_queue:
            await event_queue.put(('completed', event_data))
        else:
            yield json.dumps(event_data)

    except Exception as e:
        logger.error(
            "Agent execution failed - session_id: %s, error: %s",
            session_id, str(e)
        )
        raise
