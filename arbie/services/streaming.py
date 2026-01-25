"""Streaming utilities for agent execution.

Provides formatted console output for stream events during agent execution.
"""

import json
from typing import Any

from agents import (
    AgentUpdatedStreamEvent,
    ItemHelpers,
    RawResponsesStreamEvent,
    RunItemStreamEvent,
    StreamEvent,
)

# ANSI color codes for console output
COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "cyan": "\033[36m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "magenta": "\033[35m",
    "blue": "\033[34m",
    "red": "\033[31m",
}


def _truncate(text: str, max_length: int = 500) -> str:
    """Truncate text if it exceeds max_length."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + f"... ({len(text) - max_length} more chars)"


def _format_args(args: Any) -> str:
    """Format tool arguments for display."""
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return _truncate(args)

    if isinstance(args, dict):
        # Format dict nicely, truncating long values
        formatted_parts = []
        for key, value in args.items():
            str_value = str(value)
            if len(str_value) > 100:
                str_value = str_value[:100] + "..."
            formatted_parts.append(f"  {key}: {str_value}")
        return "\n" + "\n".join(formatted_parts) if formatted_parts else "{}"

    return _truncate(str(args))


async def print_stream_event(event: StreamEvent) -> None:
    """Print formatted stream events to console.

    Handles different event types with appropriate formatting:
    - tool_called: Shows tool name and arguments
    - tool_output: Shows tool result (truncated)
    - handoff events: Shows agent transition info
    - agent_updated: Shows new agent name
    - message_output: Shows generated message

    Args:
        event: The stream event to print.
    """
    c = COLORS  # shorthand

    if event.type == "agent_updated_stream_event":
        agent_event: AgentUpdatedStreamEvent = event
        agent_name = agent_event.new_agent.name
        print(f"\n{c['bold']}{c['magenta']}[Agent] {agent_name}{c['reset']}")

    elif event.type == "run_item_stream_event":
        item_event: RunItemStreamEvent = event
        item = item_event.item
        name = item_event.name

        if name == "tool_called":
            # Tool call initiated - access raw_item for tool details
            raw_item = getattr(item, "raw_item", item)
            tool_name = getattr(raw_item, "name", "unknown")
            raw_args = getattr(raw_item, "arguments", "{}")
            formatted_args = _format_args(raw_args)
            print(f"\n{c['cyan']}[Tool Call] {c['bold']}{tool_name}{c['reset']}")
            if formatted_args.strip():
                print(f"{c['dim']}{formatted_args}{c['reset']}")

        elif name == "tool_output":
            # Tool returned result
            output = getattr(item, "output", "")
            output_str = str(output) if output else "(no output)"
            truncated = _truncate(output_str, 300)
            print(f"{c['green']}[Tool Output] {truncated}{c['reset']}")

        elif name == "handoff_requested":
            # Handoff to another agent requested
            target = getattr(item, "target_agent", None)
            target_name = target.name if target else "unknown"
            print(f"\n{c['yellow']}[Handoff Requested] -> {target_name}{c['reset']}")

        elif name == "handoff_occured":
            # Handoff completed
            target = getattr(item, "target_agent", None)
            target_name = target.name if target else "unknown"
            print(f"{c['yellow']}[Handoff Complete] Now running: {target_name}{c['reset']}")

        elif name == "message_output_created":
            # Final message output - we'll skip printing here as final output
            # is printed separately at the end
            pass

        elif name == "reasoning_item_created":
            # Reasoning step (if model supports it)
            print(f"{c['dim']}[Reasoning] ...{c['reset']}")

        elif name in ("mcp_approval_requested", "mcp_approval_response", "mcp_list_tools"):
            # MCP-related events
            print(f"{c['dim']}[MCP] {name}{c['reset']}")

    elif event.type == "raw_response_event":
        # We skip raw token events by default to reduce noise
        # Uncomment below for token-by-token streaming:
        # raw_event: RawResponsesStreamEvent = event
        # if hasattr(event.data, "delta"):
        #     print(event.data.delta, end="", flush=True)
        pass
