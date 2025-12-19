"""
Request Context Management

Provides context variables for tracking request IDs throughout
the request lifecycle using Python's contextvars module for thread-safe
and async-safe context propagation.
"""

from contextvars import ContextVar
import uuid
from typing import Optional


# Context variable for request tracking
# This is thread-safe and async-safe, perfect for FastAPI
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)


def generate_request_id() -> str:
    """
    Generate a new UUID v4 request ID.

    Returns:
        str: A new UUID v4 string
    """
    return str(uuid.uuid4())


def set_request_context(request_id: Optional[str]) -> None:
    """
    Set the request ID in the current context.

    Args:
        request_id: The request identifier (from X-Request-ID header or generated)
    """
    request_id_var.set(request_id)


def get_request_id() -> Optional[str]:
    """
    Get the request ID from the current context.

    Returns:
        Optional[str]: The request ID, or None if not set
    """
    return request_id_var.get()


def clear_request_context() -> None:
    """
    Clear the request context by resetting the request ID.
    Should be called in the finally block of request processing.
    """
    request_id_var.set(None)
