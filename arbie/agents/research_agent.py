"""Research Agent - Regulatory compliance specialist.

Handles questions about short-term rental regulations and compliance
using web search to find current permit, tax, and registration requirements.
"""

from agents import Agent
from pathlib import Path

from arbie.tools.research_tools import web_search, todo


# Load instructions from markdown file
INSTRUCTIONS_PATH = Path(__file__).parent / "prompts" / "research_agent_instructions.md"
with open(INSTRUCTIONS_PATH) as f:
    RESEARCH_AGENT_INSTRUCTIONS = f.read()


research_agent = Agent(
    name="Research Agent",
    instructions=RESEARCH_AGENT_INSTRUCTIONS,
    tools=[web_search, todo],
    model="gpt-4o",
)
