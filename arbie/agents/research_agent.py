"""Research Agent - Regulatory compliance specialist.

Handles questions about short-term rental regulations and compliance.
"""

from agents import Agent
from pathlib import Path


# Load instructions from markdown file
INSTRUCTIONS_PATH = Path(__file__).parent / "prompts" / "research_agent_instructions.md"
with open(INSTRUCTIONS_PATH) as f:
    RESEARCH_AGENT_INSTRUCTIONS = f.read()


research_agent = Agent(
    name="Research Agent",
    instructions=RESEARCH_AGENT_INSTRUCTIONS,
    tools=[],  # No tools yet - web search coming in future iteration
    model="gpt-5.2"
)
