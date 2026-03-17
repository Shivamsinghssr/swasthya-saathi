"""
main.py — Swasthya Saathi v5.0

Phase 1: POST /chat             — text agent
Phase 2: WS   /ws/voice         — real-time voice
Phase 3: POST /chat/image       — prescription image analysis
Phase 4: Docker + Langfuse + eval harness
Phase 5: Multi-turn memory + Admin dashboard (NEW)
         GET/POST /admin/*      — password-protected dashboard
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import os
import time

from langchain_core.messages import HumanMessage, AIMessage

import config
from agent.graph import get_graph
from agent.tools import init_tools
from agent.image_tool import analyze_prescription_image
from rag.indexer import load_or_build_indexes
from api.voice import router as voice_router, init_voice_runner
from api.admin import router as admin_router          # Phase 5 NEW
from memory.session_store import get_session_store    # Phase 5 NEW
from memory.query_logger import get_query_logger      # Phase 5 NEW


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n🚀 Starting Swasthya Saathi v5...")

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
    init_voice_runner()

    # Phase 5: initialize memory and logger
    get_session_store()    # connects Redis (or falls back to memory)
    get_query_logger()     # connects Redis (or falls back to memory)

    print("\n✅ Swasthya Saathi ready to serve!\n")
    yield
    print("👋 Shutting down.")


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Swasthya Saathi API",
    description="Hindi-first health assistant for rural UP and Bihar",
    version="5.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(voice_router)
app.include_router(admin_router)   # Phase 5 NEW


# ── Schemas ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    model_config = {"json_schema_extra": {"example": {
        "message": "mujhe 3 din se bukhar hai",
        "session_id": "user_abc123"
    }}}


class ChatResponse(BaseModel):
    response: str
    tools_used: List[str]
    session_id: str


class ImageRequest(BaseModel):
    image_base64: str
    mime_type: str = "image/jpeg"
    session_id: str = "web"


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    graph         = get_graph()
    session_store = get_session_store()
    query_logger  = get_query_logger()
    start_time    = time.time()

    # ── Build message history (Phase 5: multi-turn memory) ────────────────────
    history  = session_store.get_history(request.session_id)
    messages = []

    # Convert stored history to LangChain message objects
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))

    # Add current message
    messages.append(HumanMessage(content=request.message))

    # ── Run agent ─────────────────────────────────────────────────────────────
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: graph.invoke({"messages": messages})
        )
        success = True
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    latency = time.time() - start_time

    # ── Extract response ───────────────────────────────────────────────────────
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

    # ── Save to memory (Phase 5) ───────────────────────────────────────────────
    session_store.add_message(request.session_id, "user",      request.message)
    session_store.add_message(request.session_id, "assistant", response_text)

    # ── Log query (Phase 5) ────────────────────────────────────────────────────
    query_logger.log(
        session_id      = request.session_id,
        query           = request.message,
        tools_used      = tools_used,
        latency_s       = latency,
        response_length = len(response_text),
        success         = success,
    )

    return ChatResponse(
        response   = response_text,
        tools_used = tools_used,
        session_id = request.session_id,
    )


@app.post("/chat/image", response_model=ChatResponse)
async def chat_image(request: ImageRequest):
    if not request.image_base64:
        raise HTTPException(status_code=400, detail="image_base64 is required.")

    query_logger = get_query_logger()
    start_time   = time.time()

    loop = asyncio.get_event_loop()
    response_text = await loop.run_in_executor(
        None,
        lambda: analyze_prescription_image(request.image_base64, request.mime_type)
    )

    query_logger.log(
        session_id      = request.session_id,
        query           = "[prescription image]",
        tools_used      = ["prescription_image_analyzer"],
        latency_s       = time.time() - start_time,
        response_length = len(response_text),
    )

    return ChatResponse(
        response   = response_text,
        tools_used = ["prescription_image_analyzer"],
        session_id = request.session_id,
    )


@app.delete("/chat/session/{session_id}")
async def clear_session(session_id: str):
    """Clear conversation history for a session."""
    get_session_store().clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="ok", service="Swasthya Saathi", version="5.0.0")


@app.get("/tools")
async def list_tools():
    from agent.tools import ALL_TOOLS
    return {
        "tools": [
            {"name": t.name, "description": t.description.strip().split("\n")[0]}
            for t in ALL_TOOLS
        ]
    }


# ── Static files — MUST be last ────────────────────────────────────────────────
if os.path.exists("frontend"):
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
