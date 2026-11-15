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
from .copilot import (
    CopilotContextTooLarge,
    ask_copilot,
    build_copilot_context,
    build_copilot_messages,
)
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
    "CopilotContextTooLarge",
    "LlmConfig",
    "LlmError",
    "MoveAction",
    "OpenAiCompatClient",
    "Proposal",
    "ProposalError",
    "RestAction",
    "ask_copilot",
    "build_context",
    "build_copilot_context",
    "build_copilot_messages",
    "build_messages",
    "feedback_message",
    "narrate_with_llm",
    "parse_proposal",
    "to_command",
]
