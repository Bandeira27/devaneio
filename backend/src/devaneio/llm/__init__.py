"""LLM opcional: só PROPÕE. Toda mudança de estado passa pelo motor."""

from .actions import (
    EXAMPLE_PROPOSAL,
    MAX_ACTIONS,
    Action,
    AttackAction,
    CheckAction,
    MoveAction,
    Proposal,
    ProposalError,
    RestAction,
    parse_proposal,
    to_command,
)
from .client import ChatClient, OpenAiCompatClient
from .config import LlmConfig
from .errors import LlmError
from .narration import narrate_with_llm
from .prompts import build_context, build_messages, feedback_message

__all__ = [
    "EXAMPLE_PROPOSAL",
    "MAX_ACTIONS",
    "Action",
    "AttackAction",
    "ChatClient",
    "CheckAction",
    "LlmConfig",
    "LlmError",
    "MoveAction",
    "OpenAiCompatClient",
    "Proposal",
    "ProposalError",
    "RestAction",
    "build_context",
    "build_messages",
    "feedback_message",
    "narrate_with_llm",
    "parse_proposal",
    "to_command",
]
