"""
main.py — FastAPI app for Swasthya Saathi.

Phase 1: POST /chat       — text agent
Phase 2: WS   /ws/voice   — real-time voice (NEW — 4 lines added)
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
import asyncio
import os

from langchain_core.messages import HumanMessage

from agent.graph import get_graph
from agent.tools import init_tools
from rag.indexer import load_or_build_indexes

# Phase 2 imports — NEW
from api.voice import router as voice_router, init_voice_runner


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
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

    get_graph()

    # Phase 2: init voice runner — NEW
    init_voice_runner()

    print("\n✅ Swasthya Saathi ready to serve!\n")
    yield
    print("👋 Shutting down.")


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Swasthya Saathi API",
    description="Hindi-first health assistant for rural UP and Bihar",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Phase 2: mount voice WebSocket router — NEW
app.include_router(voice_router)

# # Serve frontend static files
# if os.path.exists("frontend"):
#     app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


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
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    graph = get_graph()
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: graph.invoke({"messages": [HumanMessage(content=request.message)]})
    )

    final_message = result["messages"][-1]
    response_text = (
        final_message.content
        if isinstance(final_message.content, str)
        else str(final_message.content)
    )

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
        version = "2.0.0",
    )


@app.get("/tools")
async def list_tools():
    from agent.tools import ALL_TOOLS
    return {
        "tools": [
            {"name": t.name, "description": t.description.strip().split("\n")[0]}
            for t in ALL_TOOLS
        ]
    }
# Serve frontend static files
if os.path.exists("frontend"):
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")