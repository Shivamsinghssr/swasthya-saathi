"""
main.py — FastAPI app for Swasthya Saathi.

Endpoints:
    POST /chat       — Main agent endpoint
    GET  /health     — Service health check
    GET  /tools      — List available tools (useful for demos)
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import asyncio

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from agent.graph import get_graph
from agent.tools import init_tools
from rag.indexer import load_or_build_indexes


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load indexes and init tools before serving requests."""
    print("\n🚀 Starting Swasthya Saathi...")

    loop = asyncio.get_event_loop()
    retrievers, health_centers = await loop.run_in_executor(
        None, load_or_build_indexes
    )

    init_tools(
        symptom_retriever  = retrievers["symptoms"],
        medicine_retriever = retrievers["medicines"],
        scheme_retriever   = retrievers["schemes"],
        health_centers     = health_centers,
    )

    # Pre-build graph (avoids cold start on first request)
    get_graph()

    print("\n✅ Swasthya Saathi ready to serve!\n")
    yield
    print("👋 Shutting down.")


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Swasthya Saathi API",
    description="Hindi-first health assistant for rural UP and Bihar",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schemas ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"

    model_config = {"json_schema_extra": {"example": {"message": "mujhe 3 din se bukhar hai"}}}


class ChatResponse(BaseModel):
    response: str
    tools_used: List[str]
    session_id: str


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main agent endpoint.
    
    Sends user message to LangGraph ReAct agent.
    Agent decides which tools to call (symptom_checker, medicine_explainer, etc.)
    Returns grounded Hindi response.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    graph = get_graph()

    # Run graph — thread pool so we don't block the event loop
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: graph.invoke({"messages": [HumanMessage(content=request.message)]})
    )

    # ── Extract final text response ────────────────────────────────────────────
    final_message = result["messages"][-1]
    response_text = (
        final_message.content
        if isinstance(final_message.content, str)
        else str(final_message.content)
    )

    # ── Extract which tools were called ───────────────────────────────────────
    tools_used = []
    for msg in result["messages"]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_name = tc.get("name", "") if isinstance(tc, dict) else tc.name
                if tool_name and tool_name not in tools_used:
                    tools_used.append(tool_name)

    return ChatResponse(
        response   = response_text,
        tools_used = tools_used,
        session_id = request.session_id,
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status  = "ok",
        service = "Swasthya Saathi",
        version = "1.0.0",
    )


@app.get("/tools")
async def list_tools():
    """List all available agent tools — useful for README demos."""
    from agent.tools import ALL_TOOLS
    return {
        "tools": [
            {
                "name": t.name,
                "description": t.description.strip().split("\n")[0],
            }
            for t in ALL_TOOLS
        ]
    }
