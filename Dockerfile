FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN pip install uv && uv sync --frozen
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY mcp_server.py ./
CMD ["uv", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
