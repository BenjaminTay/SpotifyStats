"""Request-scoped context helpers."""

from __future__ import annotations

from contextvars import ContextVar

REQUEST_ID_HEADER = "X-Request-ID"

_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    """Return the current request id, or '-' outside a request."""
    return _request_id.get()


def set_request_id(request_id: str):
    """Set request id for the current context and return the reset token."""
    return _request_id.set(request_id)


def reset_request_id(token) -> None:
    """Reset request id to the value before ``set_request_id``."""
    _request_id.reset(token)
