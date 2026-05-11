from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    tool_calls_made: List[str] = []
    rag_context_used: bool = False
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class IndexStatusResponse(BaseModel):
    status: str
    document_count: int
    collection_name: str
    vector_store_type: str


class HealthResponse(BaseModel):
    status: str
    ollama_reachable: bool
    vector_store_ready: bool
    model: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
