import json
import logging
import asyncio
from typing import AsyncIterator, Optional
from agents import Agent, Runner, RunConfig, SQLiteSession
from agents.items import TResponseInputItem


logger = logging.getLogger(__name__)


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
            max_turns=100,
        )

        # Track state for event handling
        tool_call_count = 0

        # Stream events
        async for event in result.stream_events():
            # Handle reasoning deltas
            if event.type == "raw_response_event":
                if (
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
        final_output_text = str(result.final_output) if result.final_output else ""

        # Send final response (agent's natural completion)
        event_data = {
            'type': 'final_response',
            'content': final_output_text or 'Task execution completed',
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