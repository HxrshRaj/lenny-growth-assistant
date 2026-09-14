FROM python:3.11-slim

WORKDIR /app

# psycopg[binary] avoids needing libpq-dev; kept minimal build deps otherwise
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake the embedding model into the image at build time. Without this, every
# fresh container (a plain restart doesn't re-download, but --force-recreate,
# a rebuild, or a bind-mount volume swap all do) re-downloads ~90MB from
# HuggingFace on the *first request*, which also silently fails if the
# container has no outbound network at that moment -- discovered live (see
# agent-transcripts/phase-3-agent-layer.md). Baking it in makes startup fast
# and removes a runtime dependency on HF connectivity entirely.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
