import os
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model

from .configuration import Configuration
from .prompts import assistant_instructions
from .state import AssistantState
from .tools import query_database, web_search

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

settings = Configuration.from_runnable_config()

model = init_chat_model(
    model=settings.openai_model,
    model_provider="openai",
    api_key=os.environ["OPENAI_API_KEY"],
).bind(parallel_tool_calls=False)

graph = create_agent(
    model=model,
    tools=[query_database, web_search],
    system_prompt=assistant_instructions,
    state_schema=AssistantState,
)

assistant = graph
