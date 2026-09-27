"""Worker ownership context used to fence late task writes.

The task host sets this context after claiming a lease. Repository writes made
by that worker are then accepted only while both owner and generation still
match. HTTP control requests intentionally run without this context.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass


@dataclass(frozen=True)
class TaskExecutionIdentity:
    task_id: str
    lease_owner: str
    lease_generation: int


_identity: ContextVar[TaskExecutionIdentity | None] = ContextVar(
    "ai_task_execution_identity",
    default=None,
)


def current_execution_identity() -> TaskExecutionIdentity | None:
    return _identity.get()


def bind_execution_identity(identity: TaskExecutionIdentity) -> Token:
    return _identity.set(identity)


def reset_execution_identity(token: Token) -> None:
    _identity.reset(token)
