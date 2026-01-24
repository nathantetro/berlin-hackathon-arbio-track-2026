"""Arbie - AI Agent for Property Onboarding.

Entry point for Tower.dev execution.
"""

import os
from agents import Runner
from arbie.agents.arbie_agent import arbie_agent


def main() -> int:
    """Main entry point for Arbie agent."""
    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        print("Please set your OpenAI API key:")
        print("  export OPENAI_API_KEY='sk-...'")
        print("Or use Tower secrets:")
        print("  tower secrets create OPENAI_API_KEY sk-...")
        return 1

    print("Arbie v0.1.0 - Property Onboarding Agent")
    print("=" * 60)

    # Test prompt that exercises the agent workflow
    test_prompt = """
Hi Arbie! Please review the property submission for this session.

Tasks:
1. Get an overview of the session materials
2. Read the property guide document
3. Extract and record key property information
4. Write notes about what information is missing
5. Update the session status appropriately

Please walk through these steps and let me know what you find.
"""

    print(f"Test Prompt:\n{test_prompt}\n")
    print("=" * 60)
    print("Running agent...\n")

    # Run agent synchronously
    try:
        result = Runner.run_sync(
            agent=arbie_agent,
            input=test_prompt
        )

        print("\n" + "=" * 60)
        print("Agent Response:")
        print("=" * 60)
        print(result.final_output)
        print("\n" + "=" * 60)

        return 0

    except Exception as e:
        print(f"\nError running agent: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
