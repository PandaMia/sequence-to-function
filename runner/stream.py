import json
import logging
from typing import AsyncIterator
from agents import Agent, Runner, RunConfig, SQLiteSession, trace
from agents.items import TResponseInputItem


logger = logging.getLogger(__name__)


async def run_agent_stream(
    agent: Agent,
    initial_input: list[TResponseInputItem],
    sql_session: SQLiteSession,
    run_config: RunConfig,
    session_id: str,
) -> AsyncIterator[str]:
    """
    Run agent with streaming output.

    Args:
        agent: The agent to run
        initial_input: Initial input with user prompt
        sql_session: SQLiteSession session for persistence
        run_config: Run configuration
        session_id: Session ID for tracing

    Yields:
        SSE events as strings
    """
    with trace("stf-agent", group_id=session_id):
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
                        yield json.dumps({
                            'type': 'reasoning_delta',
                            'content': event.data.delta,
                        })

                # Handle run items
                elif event.type == "run_item_stream_event":
                    if event.item.type == "reasoning_item":
                        logger.debug(
                            {"session_id": session_id},
                            "Reasoning completed",
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
                            {
                                "session_id": session_id,
                                "tool": tool_name,
                                "tool_call_count": tool_call_count,
                                "args": tool_args,
                            },
                            "Tool called",
                        )

                        # Stream tool call to client
                        yield json.dumps({
                            'type': 'tool_call',
                            'tool': tool_name,
                            'arguments': tool_args,
                        })

                    elif event.item.type == "tool_call_output_item":
                        output = event.item.output

                        logger.debug(
                            "Tool output received",
                            {
                                "session_id": session_id,
                                "output_preview": str(output)[:200],
                                "has_visual_feedback": "VISUAL FEEDBACK:"
                                in str(output),
                            },
                        )

                        # Stream tool output to client
                        yield json.dumps({
                            'type': 'tool_output',
                            'content': str(output),
                        })

            # Agent completed - final_output is the response
            logger.info(
                {
                    "session_id": session_id,
                    "tool_calls": tool_call_count,
                },
                "Agent run completed",
            )

            # Extract final output from agent
            final_output_text = str(result.final_output) if result.final_output else ""

            # Send final response (agent's natural completion)
            yield json.dumps({
                'type': 'final_response',
                'content': final_output_text or 'Task execution completed',
            })

            yield json.dumps({
                'type': 'completed',
                'tool_calls': tool_call_count,
            })

        except Exception as e:
            logger.error(
                "Agent execution failed",
                {
                    "session_id": session_id,
                    "error": str(e),
                },
            )
            raise