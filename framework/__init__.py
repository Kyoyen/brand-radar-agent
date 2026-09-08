"""Shared model access; legacy scenario helpers load only when requested."""

from importlib import import_module

from .llm_client import LLMClient

_LEGACY = {
    "AgentRunner": ".agent_runner",
    "ContextManager": ".context_manager",
    "SessionSummarizer": ".session_summarizer",
    "PainPointIntake": ".pain_point_intake",
}


def __getattr__(name):
    if name not in _LEGACY:
        raise AttributeError(name)
    value = getattr(import_module(_LEGACY[name], __name__), name)
    globals()[name] = value
    return value

__all__ = [
    "LLMClient",
    "AgentRunner",
    "ContextManager",
    "SessionSummarizer",
    "PainPointIntake",
]
