import uuid
import httpx
from fastapi import APIRouter, HTTPException, BackgroundTasks
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from .schemas import ChatRequest, ChatResponse, IndexStatusResponse, HealthResponse
from ..agent.graph import get_agent_graph
from ..rag.store import get_vector_store, COLLECTION_NAME
from ..rag.documents import FINOPS_DOCUMENTS
from ..core.config import get_settings
from ..core.logging import logger

router = APIRouter()
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    ollama_ok = False
    try:
        headers = {}
        if settings.ollama_api_key:
            headers["Authorization"] = f"Bearer {settings.ollama_api_key}"
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", headers=headers)
            ollama_ok = resp.status_code == 200
    except Exception:
        pass
    store = get_vector_store()
    return HealthResponse(
        status="ok" if (ollama_ok and store._initialized) else "degraded",
        ollama_reachable=ollama_ok,
        vector_store_ready=store._initialized,
        model=settings.ollama_model,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())
    graph = get_agent_graph()
    try:
        result = await graph.ainvoke({
            "messages": [HumanMessage(content=request.message)],
            "rag_context": None, "retrieval_needed": None, "hop_count": 0, "query": request.message,
        })
        messages = result.get("messages", [])
        final_msg = next((m for m in reversed(messages) if isinstance(m, AIMessage) and m.content), None)
        response_text = final_msg.content if final_msg else "Could not generate a response. Please try again."
        tool_calls_made = list({tc["name"] for m in messages if isinstance(m, AIMessage) and hasattr(m, "tool_calls") for tc in (m.tool_calls or [])})
        return ChatResponse(response=response_text, session_id=session_id,
                            tool_calls_made=tool_calls_made, rag_context_used=bool(result.get("rag_context")))
    except Exception as e:
        logger.error(f"Chat error [{session_id}]: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@router.get("/index/status", response_model=IndexStatusResponse)
async def index_status():
    store = get_vector_store()
    try:
        count = store._get_client().count(COLLECTION_NAME).count if store._initialized else 0
    except Exception:
        count = 0
    vtype = ("qdrant-cloud" if settings.qdrant_url else "qdrant-persistent" if settings.qdrant_path else "qdrant-memory")
    return IndexStatusResponse(status="ready" if store._initialized else "not_initialized",
                               document_count=count, collection_name=COLLECTION_NAME, vector_store_type=vtype)


@router.post("/index/rebuild")
async def rebuild_index(background_tasks: BackgroundTasks):
    store = get_vector_store()
    store._initialized = False
    store._client = None
    background_tasks.add_task(store.initialize)
    return {"message": "Index rebuild started", "document_count": len(FINOPS_DOCUMENTS)}


@router.get("/documents")
async def list_documents():
    return {"documents": [{"id": d["id"], "title": d["title"], "category": d["category"]} for d in FINOPS_DOCUMENTS],
            "total": len(FINOPS_DOCUMENTS)}
