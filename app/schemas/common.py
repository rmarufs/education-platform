"""Common Pydantic schemas used across the application."""

from typing import Any
from pydantic import BaseModel


class SuccessResponse(BaseModel):
    """Common success response schema."""
    success: bool = True
    message: str | None = None
    data: Any = None


class ErrorResponse(BaseModel):
    """Common error response schema."""
    success: bool = False
    error: str
    detail: Any = None
