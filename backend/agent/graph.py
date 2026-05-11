"""
LangGraph ReAct agent implementing Self-RAG, HyDE, and CoRAG.
"""
import json
from typing import Annotated, TypedDict, Optional, List, Literal

from langchain_ollama import ChatOllama
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from ..core.config import get_settings
from ..core.logging import logger
from ..rag.store import get_vector_store
from ..tools.finance_tools import ALL_TOOLS
from .prompts import SYSTEM_PROMPT, HYDE_PROMPT

settings = get_settings()


class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    rag_context: Optional[str]
    retrieval_needed: Optional[bool]
    hop_count: int
    query: Optional[str]


def _build_llm(with_tools: bool = False) -> ChatOllama:
    kwargs = {
        "model": settings.ollama_model,
        "base_url": settings.ollama_base_url.rstrip("/"),
        "temperature": 0.1,
        "num_ctx": 8192,
    }
    if settings.ollama_api_key:
        kwargs["client_kwargs"] = {"headers": {"Authorization": "Bearer " + settings.ollama_api_key}}
    llm = ChatOllama(**kwargs)
    if with_tools:
        llm = llm.bind_tools(ALL_TOOLS)
    return llm


async def decide_retrieval(state: AgentState) -> AgentState:
    """Self-RAG: decide whether retrieval is needed for this query."""
    query = state.get("query") or ""
    policy_kw = [
        "policy", "budget", "threshold", "allowed", "rule", "limit", "exception",
        "approval", "compliance", "mandate", "allocation", "tag", "playbook",
        "how should", "what is the process", "when should", "who owns",
        "kpi", "metric", "rightsizing", "savings plan",
    ]
    data_only_kw = ["current spend", "latest spend", "right now", "today cost", "this month actual"]
    q = query.lower()
    has_policy = any(kw in q for kw in policy_kw)
    has_data_only = any(kw in q for kw in data_only_kw) and not has_policy
    if has_data_only:
        logger.info("Self-RAG: skipping retrieval")
        return {**state, "retrieval_needed": False}
    logger.info("Self-RAG: retrieval needed")
    return {**state, "retrieval_needed": True}


async def retrieve_context(state: AgentState) -> AgentState:
    """HyDE + hybrid retrieval with RRF fusion."""
    if not state.get("retrieval_needed", True):
        return state
    query = state.get("query") or ""
    store = get_vector_store()
    await store.initialize()
    try:
        hyde_llm = _build_llm(with_tools=False)
        hyde_resp = await hyde_llm.ainvoke([HumanMessage(content=HYDE_PROMPT.format(query=query))])
        hyde_query = hyde_resp.content.strip()
        logger.info("HyDE query: " + hyde_query[:80] + "...")
    except Exception as e:
        logger.warning("HyDE failed, using original query: " + str(e))
        hyde_query = query
    results = await store.hybrid_search(hyde_query, top_k=4)
    relevant = [r for r in results if r["rrf_score"] > 0.01]
    if not relevant:
        return {**state, "rag_context": None}
    parts = ["### [" + c["title"] + "] (score: " + str(c["rrf_score"]) + ")\n" + c["content"] for c in relevant[:3]]
    return {**state, "rag_context": "\n\n---\n\n".join(parts)}


async def agent_reason(state: AgentState) -> AgentState:
    """Core ReAct reasoning node — injects RAG context and calls tools."""
    llm = _build_llm(with_tools=True)
    ctx = state.get("rag_context")
    ctx_section = ("\n\n## Retrieved Policy Context\n" + ctx + "\n\n---\n") if ctx else ""
    system_msg = SystemMessage(content=SYSTEM_PROMPT + ctx_section)
    try:
        response = await llm.ainvoke([system_msg] + list(state["messages"]))
        tc = len(response.tool_calls) if hasattr(response, "tool_calls") else 0
        logger.info("Agent response — tool_calls: " + str(tc))
        return {**state, "messages": [response]}
    except Exception as e:
        logger.error("Agent reasoning error: " + str(e))
        return {**state, "messages": [AIMessage(content="Analysis error: " + str(e) + ". Please try again.")]}


async def corag_followup(state: AgentState) -> AgentState:
    """CoRAG: trigger additional playbook retrieval after anomalous tool results."""
    if state.get("hop_count", 0) >= 2:
        return state
    tool_results = [m for m in state["messages"] if isinstance(m, ToolMessage)]
    if not tool_results:
        return state
    try:
        td = json.loads(tool_results[-1].content)
    except Exception:
        return state
    needs = (
        td.get("anomaly_count", 0) > 0
        or "OVER BUDGET" in str(td.get("status", ""))
        or "Anomalies detected" in str(td.get("verdict", ""))
    )
    if needs and state.get("retrieval_needed") is not False:
        hop = state.get("hop_count", 0) + 1
        logger.info("CoRAG hop " + str(hop) + ": fetching playbook")
        store = get_vector_store()
        await store.initialize()
        results = await store.hybrid_search(
            "anomaly response playbook remediation escalation", top_k=2, category_filter="playbook"
        )
        if results:
            extra = "\n\n".join("### [" + r["title"] + "]\n" + r["content"] for r in results)
            base = state.get("rag_context") or ""
            return {
                **state,
                "rag_context": base + "\n\n---\n\n## Anomaly Response Playbook\n" + extra,
                "hop_count": hop,
            }
    return state


def route_after_decision(state: AgentState) -> Literal["retrieve_context", "agent_reason"]:
    return "retrieve_context" if state.get("retrieval_needed", True) else "agent_reason"


def route_after_agent(state: AgentState) -> Literal["tools", "__end__"]:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return "__end__"


def route_after_tools(state: AgentState) -> Literal["corag_followup"]:
    return "corag_followup"


def route_after_corag(state: AgentState) -> Literal["agent_reason"]:
    return "agent_reason"


def build_agent_graph():
    builder = StateGraph(AgentState)
    builder.add_node("decide_retrieval", decide_retrieval)
    builder.add_node("retrieve_context", retrieve_context)
    builder.add_node("agent_reason", agent_reason)
    builder.add_node("tools", ToolNode(ALL_TOOLS))
    builder.add_node("corag_followup", corag_followup)
    builder.set_entry_point("decide_retrieval")
    builder.add_conditional_edges(
        "decide_retrieval", route_after_decision,
        {"retrieve_context": "retrieve_context", "agent_reason": "agent_reason"},
    )
    builder.add_edge("retrieve_context", "agent_reason")
    builder.add_conditional_edges(
        "agent_reason", route_after_agent,
        {"tools": "tools", "__end__": END},
    )
    builder.add_conditional_edges(
        "tools", route_after_tools,
        {"corag_followup": "corag_followup"},
    )
    builder.add_conditional_edges(
        "corag_followup", route_after_corag,
        {"agent_reason": "agent_reason"},
    )
    return builder.compile()


_graph = None


def get_agent_graph():
    global _graph
    if _graph is None:
        _graph = build_agent_graph()
    return _graph
