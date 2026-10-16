# SQL agent

## Windows local development

Run from this directory with PostgreSQL running on localhost:5432.
The credentials and database name are loaded from `.env`.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\start-local.ps1
```

Open http://127.0.0.1:8502. The backend listens on port 8123.
Local development uses frontend port 8502 to avoid the existing frontend
on port 8501. To select another port, use `./start-local.ps1 -FrontendPort 8503`.
Logs are in `.local-logs`. The startup script sets `SQL_AGENT_DB_HOST` only
for its local processes, so `.env` can keep `host.docker.internal` for Docker.
The local LangGraph development runtime stores state locally; it is not
the production Docker deployment.

## Docker

Docker Desktop must be running and accessible to the current Windows user.

```powershell
.\.venv\Scripts\langgraph.exe build -t sql-langgraph-api:latest
docker compose up -d --build
```

Docker uses frontend port 8501 and backend port 8123. Stop the local backend
before starting the Docker backend on port 8123.
