"""
agent/graph.py — Phase 4 update

Changes from Phase 3:
  - Added Langfuse CallbackHandler (3 lines — marked NEW)
  - Everything else identical

Langfuse traces every agent run:
  - Which tools were called
  - LLM input/output tokens
  - Latency per step
  - Full conversation thread

Dashboard: https://cloud.langfuse.com
"""
import os
from functools import lru_cache
from typing import Annotated

from langchain_core.messages import BaseMessage
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

import config
from agent.tools import ALL_TOOLS


# ── Langfuse setup — NEW (3 lines) ────────────────────────────────────────────
def _get_langfuse_handler():
    """Returns Langfuse callback handler if keys are set, else None."""
    pub  = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    sec  = os.getenv("LANGFUSE_SECRET_KEY", "")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    if pub and sec:
        try:
            from langfuse.callback import CallbackHandler
            handler = CallbackHandler(public_key=pub, secret_key=sec, host=host)
            print("[Langfuse] ✅ Observability enabled")
            return handler
        except ImportError:
            print("[Langfuse] ⚠️  langfuse package not installed — skipping")
    else:
        print("[Langfuse] ℹ️  Keys not set — observability disabled")
    return None


# ── Agent State ────────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


# ── Graph Builder ──────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def get_graph():
    """
    Build and cache the LangGraph ReAct agent.
    Called once at startup via lifespan().
    """
    print("[Graph] Building LangGraph agent...")

    langfuse_handler = _get_langfuse_handler()  # NEW

    llm = ChatGroq(
        api_key=config.GROQ_API_KEY,
        model=config.LLM_MODEL,
        temperature=0,
        max_tokens=1024,
        callbacks=[langfuse_handler] if langfuse_handler else [],  # NEW
    ).bind_tools(ALL_TOOLS, parallel_tool_calls=False)

    def agent_node(state: AgentState):
        from agent.prompts import SYSTEM_PROMPT
        from langchain_core.messages import SystemMessage

        messages = state["messages"]
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)

        # Pass langfuse handler as config — NEW
        config_dict = {}
        if langfuse_handler:
            config_dict = {"callbacks": [langfuse_handler]}

        response = llm.invoke(messages, config=config_dict)  # NEW (added config)
        return {"messages": [response]}

    def tools_condition(state: AgentState):
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return END

    tools_node = ToolNode(ALL_TOOLS)

    graph = StateGraph(AgentState)
    graph.add_node("agent_node", agent_node)
    graph.add_node("tools_node", tools_node)
    graph.set_entry_point("agent_node")
    graph.add_conditional_edges("agent_node", tools_condition, {
        "tools": "tools_node",
        END: END,
    })
    graph.add_edge("tools_node", "agent_node")

    compiled = graph.compile()
    print("[Graph] ✅ Agent ready.")
    return compiled
