"""State definitions for LangGraph workflows."""
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
import operator


class CustomerState(TypedDict):
    """State for the customer (guest) workflow."""
    phone: str
    name: str
    message: str
    history: list[dict]
    is_admin: bool
    security_valid: bool
    blocked_reason: str | None
    sender_info: dict
    intent: str
    agent_response: str
    final_message: str


class AdminState(TypedDict):
    """State for the admin workflow."""
    phone: str
    name: str
    message: str
    history: list[dict]
    is_admin: bool
    security_valid: bool
    blocked_reason: str | None
    sender_info: dict
    intent: str
    agent_response: str
    final_message: str


def add_messages(left: Sequence[BaseMessage] | None, right: Sequence[BaseMessage] | None) -> list[BaseMessage]:
    """Reducer for appending messages in state."""
    if left is None:
        left = []
    if right is None:
        right = []
    return list(left) + list(right)