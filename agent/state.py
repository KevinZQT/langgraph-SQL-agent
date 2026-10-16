from typing import TypedDict, Annotated, NotRequired
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages
from langchain.agents import AgentState


class SchemaContext(TypedDict):
    tables: list[str]
    table_schema: str
    foreign_keys: str


    
class OverallState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    schema_context:SchemaContext | None
    query: str
    sql:str
    validation_passed: bool
    error: str | None
    retry_count: int
    max_retry_count: int
    results: list[dict]
    answer: str

class AssistantState(AgentState):
    schema_context: NotRequired[SchemaContext | None]
    last_sql: NotRequired[str]
    last_results: NotRequired[list[dict]]


