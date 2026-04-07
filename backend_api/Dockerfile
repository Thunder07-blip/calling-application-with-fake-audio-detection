FROM python:3.11-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY backend_api/requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

COPY backend_api/ .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
