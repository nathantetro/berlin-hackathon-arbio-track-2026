"""Utility for loading prompts with section templating."""

from pathlib import Path
import re


def load_prompt_with_sections(base_prompt_path: str | Path) -> str:
    """Load a prompt file and fill in section templates.

    Looks for {{section_name}} placeholders and replaces them with content
    from {base_name}_sections/section_name.md files.

    Args:
        base_prompt_path: Path to the main prompt file (e.g., arbie_instructions.md)

    Returns:
        Fully rendered prompt with all sections included

    Example:
        If arbie_instructions.md contains:
            "# Instructions\n{{agent_loop_rules}}\n{{workflow}}"

        This will look for sections in arbie_sections/:
            - arbie_sections/agent_loop_rules.md
            - arbie_sections/workflow.md

        If research_instructions.md contains:
            "# Instructions\n{{tools}}"

        This will look for sections in research_sections/:
            - research_sections/tools.md
    """
    base_path = Path(base_prompt_path)

    # Determine sections directory based on prompt filename
    # e.g., "arbie_instructions.md" -> "arbie_sections"
    # e.g., "research_instructions.md" -> "research_sections"
    prompt_base_name = base_path.stem.replace('_instructions', '')
    sections_dir = base_path.parent / f"{prompt_base_name}_sections"

    # Read the main prompt file
    with open(base_path) as f:
        content = f.read()

    # Find all {{section_name}} placeholders
    placeholders = re.findall(r'\{\{(\w+)\}\}', content)

    # Replace each placeholder with its section content
    for placeholder in placeholders:
        section_file = sections_dir / f"{placeholder}.md"

        if section_file.exists():
            with open(section_file) as f:
                section_content = f.read()

            # Replace the placeholder
            content = content.replace(f"{{{{{placeholder}}}}}", section_content)
        else:
            # If section file doesn't exist, raise clear error
            raise FileNotFoundError(
                f"Section file not found: {section_file}\n"
                f"Expected for placeholder: {{{{{placeholder}}}}}\n"
                f"Sections directory: {sections_dir}"
            )

    return content
