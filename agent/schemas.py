from pydantic import BaseModel,Field
from langchain_core.messages import AnyMessage

class SqlGeneration(BaseModel):
    sql: str = Field(description="The generated SQL query")
class SqlValidation(BaseModel):
    passed: bool = Field(description="Whether the SQL query passes all validation checks.")
    error: str | None = Field(
        description=(
            "Specific issues that need to be fixed. "
            "Return null if the query passes validation."
        ))

    
