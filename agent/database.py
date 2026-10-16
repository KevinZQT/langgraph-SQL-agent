import os
from pathlib import Path
from pprint import pprint
from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, inspect, text

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

database_url = URL.create(
    drivername = "postgresql+psycopg",
    username = os.environ["DB_USER"],
    password = os.environ['DB_PASSWORD'],
    host = os.getenv("SQL_AGENT_DB_HOST") or os.getenv("DB_HOST", "localhost"),
    port = int(os.getenv("DB_PORT", 5432)),
    database = os.getenv("DB_NAME", "pagila")
)

engine = create_engine(database_url, connect_args={"connect_timeout": 5})



def fetch_database_metadata() -> dict:

    with engine.connect() as connection:
        inspector = inspect(connection)
        tables = inspector.get_table_names(schema="public")
        table_descriptions = []
        foreign_key_descriptions = []

        for table in tables:

            columns = inspector.get_columns(
                table,
                schema="public"
            )

            column_descriptions = [
                f"{column['name']}: {column['type']}"
                for column in columns
            ]

            table_descriptions.append(
                f"Table public.{table}:\n"
                + "\n".join(column_descriptions)
            )

            foreign_keys = inspector.get_foreign_keys(
                table,
                schema="public"
            )

            for fk in foreign_keys:
                source_columns = ", ".join(fk["constrained_columns"])
                target_columns = ", ".join(fk["referred_columns"])
                target_schema = fk["referred_schema"] or "public"

                foreign_key_descriptions.append(
                    f"public.{table} ({source_columns}) -> "
                    f"{target_schema}.{fk['referred_table']} ({target_columns})"
                )

        return {
            "tables": tables,
            "table_schema": "\n\n".join(table_descriptions),
            "foreign_keys": "\n\n".join(foreign_key_descriptions)  
        }

def run_sql(sql:str):
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        connection.execute(text("SET LOCAL statement_timeout = '10s'"))


        result = connection.execute(text(sql))

        rows = result.mappings().fetchmany(100)

        return [
            {
                key: value if isinstance(
                    value, (str, int, float, bool)
                ) or value is None else str(value)
                for key, value in row.items()
            }
            for row in rows
]


if __name__ == "__main__":
    metadata = fetch_database_metadata()

    print("\nTables:\n")
    pprint(metadata["tables"])

    print("\nTable Schema:\n")
    print(metadata["table_schema"])

    print("\nForeign Keys\n")
    print(metadata["foreign_keys"])
