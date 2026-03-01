"""Vector store for RAG — semantic + keyword hybrid search."""

import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

CHUNK_SIZE = 512  # tokens (approx 4 chars/token)
CHUNK_OVERLAP = 64
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks by approximate token count."""
    words = text.split()
    chunk_words = chunk_size * 3 // 4  # ~0.75 words per token
    overlap_words = overlap * 3 // 4
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_words])
        if chunk.strip():
            chunks.append(chunk)
        i += chunk_words - overlap_words
    return chunks


class VectorStore:
    """Per-case vector store using sentence-transformers embeddings + BM25."""

    def __init__(self, case_id: str, data_dir: Optional[Path] = None):
        self.case_id = case_id
        self.base = (data_dir or DATA_DIR) / "cases" / case_id / "vectors"
        self.base.mkdir(parents=True, exist_ok=True)
        self._model = None
        self._embeddings: Optional[np.ndarray] = None
        self._chunks: list[dict] = []
        self._load_index()

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer("all-MiniLM-L6-v2")
            except ImportError:
                logger.warning("sentence-transformers not installed; vector search disabled")
                return None
        return self._model

    def _load_index(self):
        emb_path = self.base / "embeddings.npy"
        meta_path = self.base / "chunks.json"
        if emb_path.exists() and meta_path.exists():
            try:
                self._embeddings = np.load(str(emb_path))
                self._chunks = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning("Failed to load vector index: %s", e)
                self._embeddings = None
                self._chunks = []

    def _save_index(self):
        if self._embeddings is not None:
            np.save(str(self.base / "embeddings.npy"), self._embeddings)
        (self.base / "chunks.json").write_text(
            json.dumps(self._chunks, default=str), encoding="utf-8"
        )

    def index_documents(self, documents: list[dict]) -> int:
        """Index documents. Each doc: {id, text, metadata}. Returns chunk count."""
        model = self._get_model()
        if model is None:
            return 0

        all_chunks = []
        for doc in documents:
            chunks = _chunk_text(doc.get("text", ""))
            for i, chunk in enumerate(chunks):
                all_chunks.append({
                    "doc_id": doc.get("id", ""),
                    "chunk_index": i,
                    "text": chunk,
                    "metadata": doc.get("metadata", {}),
                })

        if not all_chunks:
            return 0

        texts = [c["text"] for c in all_chunks]
        embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        self._embeddings = np.array(embeddings, dtype=np.float32)
        self._chunks = all_chunks
        self._save_index()
        logger.info("Indexed %d chunks for case %s", len(all_chunks), self.case_id)
        return len(all_chunks)

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """Semantic search using cosine similarity."""
        model = self._get_model()
        if model is None or self._embeddings is None or len(self._chunks) == 0:
            return []

        q_emb = model.encode([query], normalize_embeddings=True)
        scores = np.dot(self._embeddings, q_emb.T).flatten()
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] < 0.1:
                continue
            chunk = self._chunks[idx].copy()
            chunk["score"] = float(scores[idx])
            results.append(chunk)
        return results

    def hybrid_search(self, query: str, top_k: int = 10) -> list[dict]:
        """Combine vector search with BM25 keyword search."""
        vector_results = self.search(query, top_k=top_k * 2)

        # Simple keyword scoring
        query_terms = set(re.findall(r"\w+", query.lower()))
        keyword_scores = {}
        for i, chunk in enumerate(self._chunks):
            text_terms = set(re.findall(r"\w+", chunk["text"].lower()))
            overlap = len(query_terms & text_terms)
            if overlap > 0:
                keyword_scores[i] = overlap / max(len(query_terms), 1)

        # Merge scores (0.7 vector + 0.3 keyword)
        combined = {}
        for r in vector_results:
            idx = self._chunks.index(r) if r in self._chunks else -1
            combined[r.get("doc_id", "") + str(r.get("chunk_index", 0))] = {
                **r,
                "score": r["score"] * 0.7 + keyword_scores.get(idx, 0) * 0.3,
            }

        for idx, ks in keyword_scores.items():
            key = self._chunks[idx].get("doc_id", "") + str(self._chunks[idx].get("chunk_index", 0))
            if key not in combined:
                chunk = self._chunks[idx].copy()
                chunk["score"] = ks * 0.3
                combined[key] = chunk

        results = sorted(combined.values(), key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def delete_index(self):
        """Remove all vector data for this case."""
        for f in self.base.iterdir():
            f.unlink()
        self._embeddings = None
        self._chunks = []
