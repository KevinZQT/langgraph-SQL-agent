from typing import Literal
from langchain_core.messages import AIMessage
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from sqlalchemy.exc import SQLAlchemyError
from .database import fetch_database_metadata, run_sql
from .schemas import SqlGeneration, SqlValidation
from .state import OverallState
from .configuration import Configuration
from .prompts import (sql_generation_instructions, 
                      sql_validation_instructions)

import os


def prepare_query(state:OverallState, config: RunnableConfig):
    
    configurable = Configuration.from_runnable_config(config)

    return {
        "query": state["messages"][-1].content,
        "sql": "",
        "validation_passed": False,
        "error": None,
        "retry_count": 0,
        "max_retry_count": configurable.max_retry_count,
        "results": [],
        "answer": "",
    }


def load_schema(state:OverallState, config: RunnableConfig):

    if state.get("schema_context") is not None:
        return {}

    schema_context = fetch_database_metadata()

    return {
        "schema_context": schema_context
    }


def generate_sql(state:OverallState, config: RunnableConfig):

    configurable = Configuration.from_runnable_config(config)
    schema = state.get("schema_context")
        
    if schema is None:
        raise ValueError("Not found schema context")

    is_retry = state["error"] is not None

    formatted_prompt = sql_generation_instructions.format(
        table_schema=schema["table_schema"],
        foreign_keys=schema["foreign_keys"],
        query=state["query"],
        is_retry=str(is_retry).lower(),
        previous_sql=state["sql"] if is_retry else "(None)",
        error=state["error"] if is_retry else "(None)",
    )

    structured_llm = init_chat_model(
        model = configurable.openai_model,
        api_key=os.environ["OPENAI_API_KEY"],
    ).with_structured_output(SqlGeneration)


    result = structured_llm.invoke(formatted_prompt)

    sql = result.sql.strip()

    return {
        "sql": sql,
        "validation_passed": False,
        "error": None,
        "retry_count": state["retry_count"] + (1 if is_retry else 0),
    }

def validate_sql(state: OverallState, config: RunnableConfig):
    configurable = Configuration.from_runnable_config(config)
    schema = state["schema_context"]
    sql = state["sql"]

    if not sql:
        return {
            "validation_passed": False,
            "error": "The SQL query is empty.",
        }

    formatted_prompt = sql_validation_instructions.format(
        table_schema=schema["table_schema"],
        foreign_keys=schema["foreign_keys"],
        query=state["query"],
        sql=state["sql"],
    )

    structured_llm = init_chat_model(
        model = configurable.openai_model,
        api_key=os.environ["OPENAI_API_KEY"],
    ).with_structured_output(SqlValidation)

    result = structured_llm.invoke(formatted_prompt)

    return {
        "validation_passed": result.passed,
        "error":         
            None
            if result.passed
            else result.error or "SQL validation failed."
    }
def failed_generate_sql(state: OverallState, config: RunnableConfig):
    response = "Unable to complete the SQL query within the retry limit."
    return {
        "answer": response,
        "messages": [AIMessage(content=response)],
    }
def route_after_validation(state:OverallState) -> Literal["accept", "reject", "failed"]:
    passed = state["validation_passed"]
    retry_count = state["retry_count"]
    max_retry_count = state["max_retry_count"]
    
    if passed:
        return "accept"
    elif retry_count >= max_retry_count:
        return "failed"
    else:
        return "reject"
    
def retrieve_sql(state:OverallState, config: RunnableConfig):

    try:
        results = run_sql(state["sql"])
        return {
            "results": results,
            "error": None,
        }
    except SQLAlchemyError as exc:
        original_error = getattr(exc, "orig", exc)
        return {
            "results": [],
            "error": str(original_error),
        }
    
def route_after_execution(
    state: OverallState, config: RunnableConfig
) -> Literal["success", "retry", "failed"]:

    if state["error"] is None:
        return "success"

    if state["retry_count"] >= state["max_retry_count"]:
        return "failed"

    return "retry"




builder = StateGraph(OverallState)

builder.add_node("prepare_query", prepare_query)
builder.add_node("load_schema", load_schema)
builder.add_node("generate_sql", generate_sql)
builder.add_node("validate_sql", validate_sql)
builder.add_node("retrieve_sql", retrieve_sql)
builder.add_node("failed_generate_sql", failed_generate_sql)

builder.add_edge(START, "prepare_query")
builder.add_edge("prepare_query", "load_schema")
builder.add_edge("load_schema", "generate_sql")
builder.add_edge("generate_sql", "validate_sql")

builder.add_conditional_edges(
    "validate_sql",
    route_after_validation,
    {
        "accept": "retrieve_sql",
        "reject": "generate_sql",
        "failed": "failed_generate_sql",
    },
)

builder.add_conditional_edges(
    "retrieve_sql",
    route_after_execution,
    {
        "success": END,
        "retry": "generate_sql",
        "failed": "failed_generate_sql",
    },
)

builder.add_edge("failed_generate_sql", END)

graph = builder.compile(checkpointer=False)


