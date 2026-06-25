"""Admin LangGraph workflow definition."""
import logging
from langgraph.graph import StateGraph, END
from agents.state import AdminState
from agents.src.guard import guard_node
from agents.src.identifier import identifier_node
from agents.src.classifier import classify_intent
from agents.src.query import query_node
from agents.src.knowledge import knowledge_node
from agents.src.payment import payment_node
from agents.src.general import general_node
from agents.src.writer import writer_node

logger = logging.getLogger(__name__)


def should_continue(state: dict) -> str:
    if not state.get("security_valid", False):
        return "blocked"
    return "continue"


def route_intent(state: dict) -> str:
    intent = state.get("intent", "general")
    return intent


def build_admin_graph():
    graph = StateGraph(AdminState)

    graph.add_node("guard", guard_node)
    graph.add_node("identifier", identifier_node)
    graph.add_node("classifier", classify_intent)
    graph.add_node("query", query_node)
    graph.add_node("knowledge", knowledge_node)
    graph.add_node("payment", payment_node)
    graph.add_node("general", general_node)
    graph.add_node("writer", writer_node)

    graph.set_entry_point("guard")

    graph.add_conditional_edges(
        "guard",
        should_continue,
        {
            "continue": "identifier",
            "blocked": "writer",
        },
    )

    graph.add_edge("identifier", "classifier")

    graph.add_conditional_edges(
        "classifier",
        route_intent,
        {
            "query": "query",
            "knowledge": "knowledge",
            "payment": "payment",
            "general": "general",
        },
    )

    graph.add_edge("query", "writer")
    graph.add_edge("knowledge", "writer")
    graph.add_edge("payment", "writer")
    graph.add_edge("general", "writer")

    graph.add_edge("writer", END)

    return graph.compile()