"""Pluggable vector stores. pgvector (Postgres) stays the default; ChromaDB is an
optional second backend behind the same small interface."""
from app.services.vectorstore.base import Hit, VectorStore
from app.services.vectorstore.chroma_store import ChromaStore

__all__ = ["Hit", "VectorStore", "ChromaStore"]
