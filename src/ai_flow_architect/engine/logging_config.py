"""Logging configuration with trace_id support using loguru contextvars."""

from contextvars import ContextVar
import shortuuid

_trace_id: ContextVar[str] = ContextVar("trace_id", default="-")


def set_trace_id(trace_id: str = None):
    """Set trace_id for current context."""
    if trace_id is None:
        trace_id = shortuuid.uuid()[:8]
    _trace_id.set(trace_id)


def get_trace_id() -> str:
    """Get current trace_id."""
    return _trace_id.get()