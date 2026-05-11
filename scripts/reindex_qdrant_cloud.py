"""
One-off script: drop and recreate the 'finops_knowledge' collection
on Qdrant Cloud, then index all documents from backend/rag/documents.py.

Credentials are read from the commented-out lines in .env so the main
.env file does not need to be modified. Run from the project root:

    python scripts/reindex_qdrant_cloud.py
"""
import hashlib
import sys
import time
from pathlib import Path

# ── resolve project root so imports work without install ──────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.rag.documents import FINOPS_DOCUMENTS

QDRANT_URL = "https://1036a54e-3193-4e6d-b7db-61be701c6a48.us-west-1-0.aws.cloud.qdrant.io"
QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIiwic3ViamVjdCI6ImFwaS1rZXk6NjVlYjRmMGQtMjA3Ny00MTAyLTg2MmEtM2RhZTY3MjQ3OWJmIn0.pFmuGGXBSQh7fBYksf-jBGb3wX7qPhF_tS6AtdCoYzw"

COLLECTION = "finops_knowledge"
EMBED_MODEL = "BAAI/bge-base-en-v1.5"
EMBED_DIM   = 768
CHUNK_SIZE  = 800
CHUNK_OVERLAP = 150


def chunk_document(doc: dict) -> list[dict]:
    words = doc["content"].strip().split()
    chunks, start, idx = [], 0, 0
    while start < len(words):
        end = min(start + CHUNK_SIZE, len(words))
        text = " ".join(words[start:end])
        cid = hashlib.md5(f"{doc['id']}-{idx}".encode()).hexdigest()[:16]
        chunks.append({
            "id": cid,
            "doc_id": doc["id"],
            "title": doc["title"],
            "category": doc["category"],
            "chunk_idx": idx,
            "content": text,
        })
        start += CHUNK_SIZE - CHUNK_OVERLAP
        idx += 1
    return chunks


def main():
    from fastembed import TextEmbedding
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

    print(f"Connecting to Qdrant Cloud: {QDRANT_URL}")
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    info = client.get_collections()
    existing = [c.name for c in info.collections]
    print(f"Existing collections: {existing}")

    if COLLECTION in existing:
        print(f"Dropping existing '{COLLECTION}'...")
        client.delete_collection(COLLECTION)
        time.sleep(1)

    print(f"Creating '{COLLECTION}' (dim={EMBED_DIM}, cosine)...")
    client.create_collection(
        COLLECTION,
        vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
    )

    print(f"Loading embedding model '{EMBED_MODEL}'...")
    embedder = TextEmbedding(EMBED_MODEL)

    all_chunks = [c for doc in FINOPS_DOCUMENTS for c in chunk_document(doc)]
    print(f"Chunked {len(FINOPS_DOCUMENTS)} documents -> {len(all_chunks)} chunks")

    points = []
    for i, chunk in enumerate(all_chunks):
        vec = list(next(iter(embedder.embed([chunk["content"]]))))
        point_id = int(hashlib.md5(chunk["id"].encode()).hexdigest()[:8], 16)
        points.append(PointStruct(id=point_id, vector=vec, payload=chunk))
        print(f"  [{i+1}/{len(all_chunks)}] embedded: {chunk['doc_id']} chunk {chunk['chunk_idx']}")

    print(f"Upserting {len(points)} vectors to Qdrant Cloud...")
    client.upsert(collection_name=COLLECTION, points=points)

    count = client.count(COLLECTION).count
    print(f"\nDone. Collection '{COLLECTION}' now has {count} vectors.")
    print(f"Qdrant Cloud URL: {QDRANT_URL}")


if __name__ == "__main__":
    main()
