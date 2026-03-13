"""
agent/graph.py

LangGraph ReAct agent for Swasthya Saathi.

Architecture:
    [START] → agent_node → (tool calls?) → tools_node → agent_node → ... → [END]

The LLM decides WHICH tools to call and in WHAT ORDER based on the user's query.
This is the key recruiter signal: real agent orchestration, not scripted logic.
""" 
from typing import Annotated
from typing_extensions import TypedDict

from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, BaseMessage

from agent.tools import ALL_TOOLS
from agent.prompts import SYSTEM_PROMPT
import config


# ── Agent State ────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    """
    State passed between nodes in the graph.
    messages: full conversation history — LangGraph handles appending automatically.
    """
    messages: Annotated[list[BaseMessage], add_messages]


# ── Graph Builder ──────────────────────────────────────────────────────────────

def build_graph():
    """
    Builds and compiles the LangGraph ReAct agent.
    Called once at startup — graph is reused across all requests.
    
    Node flow:
        agent_node: LLM decides next action (reply or tool call)
        tools_node: Executes tool calls, returns results to agent
        
    Routing:
        tools_condition: built-in LangGraph helper
        → if last message has tool_calls  → go to tools_node
        → else                            → END
    """

    # LLM with tools bound — Groq llama3.3-70b has strong tool-calling support
    llm = ChatGroq(
        api_key=config.GROQ_API_KEY,
        model=config.LLM_MODEL,
        temperature=0,
        max_tokens=1024,
    ).bind_tools(ALL_TOOLS, parallel_tool_calls=False)

    # Tool execution node — LangGraph handles invoking the right tool automatically
    tool_node = ToolNode(ALL_TOOLS)

    # ── Agent Node ────────────────────────────────────────────────────────────
    def agent_node(state: AgentState) -> dict:
        """
        Core reasoning node.
        Prepends system prompt, calls LLM, returns response.
        LLM may respond with text OR with tool_calls.
        """
        # Always inject system prompt as first message
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
        response = llm.invoke(messages)
        return {"messages": [response]}

    # ── Build Graph ───────────────────────────────────────────────────────────
    graph_builder = StateGraph(AgentState)

    graph_builder.add_node("agent", agent_node)
    graph_builder.add_node("tools", tool_node)

    # Entry point
    graph_builder.set_entry_point("agent")

    # Conditional routing: tool call → tools node, else → END
    graph_builder.add_conditional_edges(
        "agent",
        tools_condition,   # LangGraph built-in: checks for tool_calls
    )

    # After tools execute → always return to agent for reasoning
    graph_builder.add_edge("tools", "agent")

    return graph_builder.compile()


# ── Singleton ──────────────────────────────────────────────────────────────────
# Graph is built once at server startup — all requests share it (stateless graph)

_graph = None


def get_graph():
    global _graph
    if _graph is None:
        print("[Graph] Building LangGraph agent...")
        _graph = build_graph()
        print("[Graph] ✅ Agent ready.")
    return _graph
