import os
from typing import Any
from dataclasses import dataclass, fields
from langchain_core.runnables import RunnableConfig


@dataclass(kw_only=True)
class Configuration:
    thread_id: str = "default"
    max_retry_count: int = 2
    openai_model: str = "gpt-5.4-mini"

    @classmethod
    def from_runnable_config(
        cls,
        config: RunnableConfig | None = None,
    ) -> "Configuration":
        configurable = (config or {}).get("configurable", {})

        values: dict[str, Any] = {}

        for field in fields(cls):
            if not field.init:
                continue

            value = configurable.get(field.name)

            if value is None:
                value = os.environ.get(field.name.upper())

            if value is not None:
                values[field.name] = value

        for name in ("max_retry_count", "db_port"):
            if name in values:
                values[name] = int(values[name])

        if "thread_id" in values:
            values["thread_id"] = str(values["thread_id"])

        return cls(**values)