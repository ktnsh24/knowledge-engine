FROM python:3.11-slim

WORKDIR /app

# Install Poetry
RUN pip install poetry==1.8.3

# Copy dependency files first (layer caching)
COPY pyproject.toml poetry.lock* ./

# Install dependencies (no dev)
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-root --without dev

# Copy source
COPY src/ ./src/
COPY ui/ ./ui/
COPY scripts/ ./scripts/

# Create wiki output dir
RUN mkdir -p wiki-output/topics

EXPOSE 8200

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8200"]
