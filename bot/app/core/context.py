from contextvars import ContextVar, Token
from uuid import uuid4

import structlog.contextvars

_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def begin_request(request_id: str | None = None) -> Token[str]:
    value = request_id or uuid4().hex
    token = _request_id.set(value)
    structlog.contextvars.bind_contextvars(request_id=value)
    return token


def end_request(token: Token[str]) -> None:
    _request_id.reset(token)
    structlog.contextvars.clear_contextvars()


def get_request_id() -> str:
    return _request_id.get()
