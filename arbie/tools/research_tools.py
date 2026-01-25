"""Research tools for the Research Agent.

Provides web search and task tracking for compliance research.
"""

from agents import function_tool

from arbie.services.tavily_service import get_tavily_service


# In-memory todo list for research tracking (resets per handoff)
_todo_list: list[dict] = []


@function_tool
def web_search(query: str, max_results: int = 5) -> dict:
    """
    Search the web for information.

    Use this to research short-term rental regulations, permits,
    taxes, and compliance requirements for specific locations.

    Args:
        query: Search query - be specific and include location.
               Example: "Miami Beach short-term rental permit requirements 2024"
        max_results: Number of results to return (1-10, default 5)

    Returns:
        dict with:
        - query: The search query used
        - answer: AI-generated summary (if available)
        - results: List of {title, url, content, score}
        - result_count: Number of results returned
    """
    try:
        service = get_tavily_service()
        response = service.search_with_retry(
            query=query,
            max_results=max_results,
            search_depth="advanced",
        )

        return {
            "query": response.query,
            "answer": response.answer,
            "results": [
                {
                    "title": r.title,
                    "url": r.url,
                    "content": r.content,
                    "score": r.score,
                }
                for r in response.results
            ],
            "result_count": len(response.results),
        }
    except ValueError as e:
        # Missing API key or configuration error
        return {
            "status": "error",
            "message": str(e),
            "query": query,
        }
    except Exception as e:
        # Network or API error
        return {
            "status": "error",
            "message": f"Search failed: {e}",
            "query": query,
        }


@function_tool
def todo(action: str, item: str = "") -> dict:
    """
    Manage a todo list during research.

    Use this to track what you need to research and mark items complete
    as you find the information. Helps ensure thorough research coverage.

    Args:
        action: One of:
            - "add": Add a new item to research
            - "complete": Mark an item as done
            - "list": Show current todo list
        item: Todo item text (required for "add" and "complete")

    Returns:
        dict with:
        - action: The action performed
        - items: Current list of {text, completed} items
        - pending_count: Number of incomplete items
        - completed_count: Number of completed items
    """
    global _todo_list

    action = action.lower().strip()

    if action == "add":
        if not item:
            return {
                "status": "error",
                "message": "Item text required for 'add' action",
            }
        _todo_list.append({"text": item, "completed": False})

    elif action == "complete":
        if not item:
            return {
                "status": "error",
                "message": "Item text required for 'complete' action",
            }
        # Find and mark item as complete (case-insensitive partial match)
        item_lower = item.lower()
        found = False
        for todo_item in _todo_list:
            if item_lower in todo_item["text"].lower() and not todo_item["completed"]:
                todo_item["completed"] = True
                found = True
                break
        if not found:
            return {
                "status": "warning",
                "message": f"No pending item matching '{item}' found",
                "items": _todo_list,
            }

    elif action == "list":
        pass  # Just return current state

    elif action == "clear":
        _todo_list = []

    else:
        return {
            "status": "error",
            "message": f"Unknown action: {action}. Use 'add', 'complete', 'list', or 'clear'.",
        }

    pending = [t for t in _todo_list if not t["completed"]]
    completed = [t for t in _todo_list if t["completed"]]

    return {
        "action": action,
        "items": _todo_list,
        "pending_count": len(pending),
        "completed_count": len(completed),
    }


def reset_todo_list():
    """Reset the todo list. Called between research sessions."""
    global _todo_list
    _todo_list = []
