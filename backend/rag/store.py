"""
Qdrant vector store with hybrid BM25 + dense retrieval and RRF fusion.
Runs in-memory by default; persistent on disk or Qdrant Cloud via config.
"""
import asyncio
import hashlib
import statistics
from typing import List, Dict, Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue,
)
from rank_bm25 import BM25Okapi

from ..core.config import get_settings
from ..core.logging import logger
from .documents import FINOPS_DOCUMENTS

settings = get_settings()
COLLECTION_NAME = "finops_knowledge"
EMBED_DIM = 768
EMBED_MODEL_NAME = "BAAI/bge-base-en-v1.5"

_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from fastembed import TextEmbedding
        logger.info(f"Loading local embedding model '{EMBED_MODEL_NAME}'")
        _embedder = TextEmbedding(EMBED_MODEL_NAME)
    return _embedder


def _get_qdrant_client() -> QdrantClient:
    if settings.qdrant_url:
        return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
    elif settings.qdrant_path:
        return QdrantClient(path=settings.qdrant_path)
    return QdrantClient(":memory:")


class FinOpsVectorStore:
    def __init__(self):
        self._client: Optional[QdrantClient] = None
        self._documents: List[Dict] = []
        self._bm25: Optional[BM25Okapi] = None
        self._initialized = False

    def _get_client(self) -> QdrantClient:
        if self._client is None:
            self._client = _get_qdrant_client()
        return self._client

    async def _embed(self, text: str) -> List[float]:
        def _run() -> List[float]:
            vec = next(iter(_get_embedder().embed([text])))
            return vec.tolist()
        return await asyncio.to_thread(_run)

    def _chunk_document(self, doc: Dict, chunk_size: int = 800, overlap: int = 150) -> List[Dict]:
        words = doc["content"].strip().split()
        chunks, start, idx = [], 0, 0
        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_text = " ".join(words[start:end])
            cid = hashlib.md5(f"{doc['id']}-{idx}".encode()).hexdigest()[:16]
            chunks.append({"id": cid, "doc_id": doc["id"], "title": doc["title"],
                           "category": doc["category"], "chunk_idx": idx, "content": chunk_text})
            start += chunk_size - overlap
            idx += 1
        return chunks

    async def initialize(self) -> None:
        if self._initialized:
            return
        client = self._get_client()
        existing = [c.name for c in client.get_collections().collections]
        if COLLECTION_NAME not in existing:
            logger.info(f"Creating Qdrant collection '{COLLECTION_NAME}'")
            client.create_collection(COLLECTION_NAME, vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE))
            await self._index_documents()
        else:
            count = client.count(COLLECTION_NAME).count
            logger.info(f"Collection '{COLLECTION_NAME}' has {count} vectors")
            if count == 0:
                await self._index_documents()
        await self._build_bm25()
        self._initialized = True

    async def _index_documents(self) -> None:
        client = self._get_client()
        all_chunks = [chunk for doc in FINOPS_DOCUMENTS for chunk in self._chunk_document(doc)]
        logger.info(f"Indexing {len(all_chunks)} chunks...")
        points = []
        for chunk in all_chunks:
            try:
                vector = await self._embed(chunk["content"])
                points.append(PointStruct(
                    id=int(hashlib.md5(chunk["id"].encode()).hexdigest()[:8], 16),
                    vector=vector,
                    payload=chunk,
                ))
            except Exception as e:
                logger.warning(f"Embed failed for chunk {chunk['id']}: {e}")
        if points:
            client.upsert(collection_name=COLLECTION_NAME, points=points)
            logger.info(f"Indexed {len(points)} chunks")

    async def _build_bm25(self) -> None:
        client = self._get_client()
        results = client.scroll(COLLECTION_NAME, limit=1000, with_payload=True, with_vectors=False)
        self._documents = [r.payload for r in results[0]]
        tokenized = [d["content"].lower().split() for d in self._documents]
        if tokenized:
            self._bm25 = BM25Okapi(tokenized)
        logger.info(f"BM25 index built over {len(self._documents)} chunks")

    async def hybrid_search(self, query: str, top_k: int = 5, category_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self._initialized:
            await self.initialize()
        client = self._get_client()
        query_vector = await self._embed(query)
        qdrant_filter = None
        if category_filter:
            qdrant_filter = Filter(must=[FieldCondition(key="category", match=MatchValue(value=category_filter))])
        dense_response = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=top_k * 2,
            query_filter=qdrant_filter,
            with_payload=True,
        )
        dense_results = dense_response.points
        dense_ids = {str(r.id): (rank + 1, r.payload) for rank, r in enumerate(dense_results)}

        bm25_ids = {}
        if self._bm25 and self._documents:
            scores = self._bm25.get_scores(query.lower().split())
            for rank, (idx, score) in enumerate(sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k * 2]):
                if score > 0:
                    doc = self._documents[idx]
                    bm25_ids[doc.get("id", str(idx))] = (rank + 1, doc)

        k = 60
        rrf_scores: Dict[str, float] = {}
        all_docs: Dict[str, Dict] = {}
        for chunk_id, (rank, payload) in dense_ids.items():
            pid = payload.get("id", chunk_id)
            rrf_scores[pid] = rrf_scores.get(pid, 0) + 1 / (k + rank)
            all_docs[pid] = payload
        for chunk_id, (rank, payload) in bm25_ids.items():
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + 1 / (k + rank)
            all_docs[chunk_id] = payload

        sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [{"id": cid, "title": all_docs[cid].get("title", ""), "category": all_docs[cid].get("category", ""),
                 "content": all_docs[cid].get("content", ""), "rrf_score": round(score, 4)}
                for cid, score in sorted_results if cid in all_docs]


_store: Optional[FinOpsVectorStore] = None


def get_vector_store() -> FinOpsVectorStore:
    global _store
    if _store is None:
        _store = FinOpsVectorStore()
    return _store
