import json
import os
from uuid import uuid4

import requests

API_URL = os.getenv("API_URL", "http://127.0.0.1:8123").rstrip("/")
ASSISTANT_ID = os.getenv("LANGGRAPH_ASSISTANT_ID", "sql_agent")


def create_thread() -> str:
    """Create a durable conversation and return the server-generated thread ID."""
    response = requests.post(f"{API_URL}/threads", json={}, timeout=(10, 30))
    response.raise_for_status()
    return response.json()["thread_id"]


def extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content or "")


def normalize_run_result(state: dict, thread_id: str, user_message_id: str) -> dict:
    """Preserve the UI's SQL preview fields from LangGraph's native state."""
    messages = state.get("messages", [])
    if not isinstance(messages, list):
        raise ValueError("LangGraph returned an invalid messages state")

    # returns the full thread history
    turn_start = next(
        (index for index, item in enumerate(messages)
         if isinstance(item, dict) and item.get("id") == user_message_id),
        None,
    )
    if turn_start is None:
        # Compatibility fallback for servers normalizing message IDs.
        turn_start = next(
            (index for index in range(len(messages) - 1, -1, -1)
             if isinstance(messages[index], dict)
             and messages[index].get("type") in ("human", "user")),
            -1,
        )

    current_messages = messages[turn_start + 1:]
    tool_messages = [
        item for item in current_messages
        if isinstance(item, dict)
        and item.get("type") == "tool"
        and item.get("name") == "query_database"
    ]

    database_used = bool(tool_messages)
    tool_data = {}
    if database_used:
        content = tool_messages[-1].get("content")
        if isinstance(content, str):
            try:
                tool_data = json.loads(content)
            except json.JSONDecodeError:
                pass
        elif isinstance(content, dict):
            tool_data = content

    answer = ""
    for message in reversed(current_messages):
        if isinstance(message, dict) and message.get("type") in ("ai", "assistant"):
            answer = extract_text(message.get("content", ""))
            break

    results = state.get("last_results", []) if database_used else []
    return {
        "session_id": thread_id,
        "answer": answer,
        "database_used": database_used,
        "sql": state.get("last_sql") if database_used else None,
        "results": results,
        "query_status": tool_data.get("status"),
        "query_error": tool_data.get("error"),
        "preview_only": tool_data.get("preview_only", False),
    }


def run_chat(thread_id: str, question: str) -> dict:
    if not question.strip() or len(question) > 4000:
        raise ValueError("The question must contain 1 to 4000 characters")

    user_message_id = str(uuid4())
    response = requests.post(
        f"{API_URL}/threads/{thread_id}/runs/wait",
        json={
            "assistant_id": ASSISTANT_ID,
            "input": {
                "messages": [
                    {"type": "human", "content": question.strip(), "id": user_message_id}
                ]
            },
            "config": {"recursion_limit": 30},
        },
        timeout=(10, 600),
    )
    response.raise_for_status()
    state = response.json()
    if isinstance(state, dict) and "__error__" in state:
        error = state["__error__"]
        message = error.get("message", str(error)) if isinstance(error, dict) else str(error)
        raise ValueError(f"LangGraph run failed: {message}")
    return normalize_run_result(state, thread_id, user_message_id)
