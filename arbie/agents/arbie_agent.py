"""Arbie Agent - Main property onboarding agent.

Coordinates the property onboarding process using file, vision, property,
email, and session management tools.
"""

from agents import Agent
from pathlib import Path

# Import all tools
from arbie.tools.file_tools import (
    get_session_overview,
    list_files,
    read_file,
    write_file
)
from arbie.tools.vision_tools import analyze_images
from arbie.tools.property_tools import edit_property, get_property
from arbie.tools.email_tools import send_email, fetch_emails
from arbie.tools.generation_tools import generate_pdf
from arbie.tools.session_tools import update_session

# Import research agent for handoffs
from arbie.agents.research_agent import research_agent

# Import prompt loader
from arbie.agents.prompt_loader import load_prompt_with_sections


# Load instructions from markdown file with sections
INSTRUCTIONS_PATH = Path(__file__).parent / "prompts" / "arbie_instructions.md"
ARBIE_INSTRUCTIONS = load_prompt_with_sections(INSTRUCTIONS_PATH)


arbie_agent = Agent(
    name="Arbie",
    instructions=ARBIE_INSTRUCTIONS,
    tools=[
        # File tools
        get_session_overview,
        list_files,
        read_file,
        write_file,
        # Vision tools
        analyze_images,
        # Property tools
        edit_property,
        get_property,
        # Email tools
        send_email,
        fetch_emails,
        # Generation tools
        generate_pdf,
        # Session tools
        update_session
    ],
    handoffs=[research_agent],
    model="gpt-5.2"
)
