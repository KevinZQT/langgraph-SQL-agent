from pathlib import Path
from dotenv import load_dotenv
from langgraph.types import Command
from langchain.tools import ToolRuntime, tool
from .graph import graph as sql_graph
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_tavily import TavilySearch
import json

load_dotenv(Path(__file__).resolve().parent.parent / ".env")



@tool
def query_database(
    question: str,
    runtime: ToolRuntime,
) -> Command:
    """Query PostgreSQL using the validated SQL workflow.

    Supply a self-contained question with the relevant context,
    names and filters resolved from the conversation.
    """
    result = sql_graph.invoke(
        {
            "messages": [HumanMessage(content=question)],
            "schema_context": runtime.state.get("schema_context"),
        },
        config=runtime.config,
    )

    # The graph state is serialized by LangGraph Server, without the old
    # FastAPI JSON conversion. Convert Decimal, dates, UUIDs, etc. here.
    rows = json.loads(json.dumps(result["results"], ensure_ascii=False, default=str))

    results_text = json.dumps(
        rows,
        ensure_ascii=False,
        default=str,
    )

    preview_only = len(results_text) > 6000

    if preview_only:
        preview = rows[:5]
        results_text = json.dumps(
            preview,
            ensure_ascii=False,
            default=str,
        )

        if len(results_text) > 6000:
            preview = []
    else:
        preview = rows

    tool_result = {
        "status": "failed" if result["error"] else "success",
        "sql": result["sql"],
        "retrieved_row_count": len(rows),
        "preview_only": preview_only,
        "preview": preview,
        "error": (
            "The SQL workflow failed within its retry limit."
            if result["error"]
            else None
        ),
    }

    return Command(
        update={
            "schema_context": result["schema_context"],
            "last_sql": result["sql"],
            "last_results": rows,
            "messages": [
                ToolMessage(
                    name="query_database",
                    content=json.dumps(
                        tool_result,
                        ensure_ascii=False,
                        default=str,
                    ),
                    tool_call_id=runtime.tool_call_id,
                )
            ],
        }
    )


tavily_search = TavilySearch(
    max_results=3,
    include_raw_content=False,
)


@tool
def web_search(query: str) -> dict:
    """Search the public web for current or externally verifiable information.

    Provide a self-contained search query with references resolved
    from the conversation. Do not include credentials or private data.
    """
    return tavily_search.invoke({"query": query})