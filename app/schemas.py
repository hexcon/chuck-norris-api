"""Pydantic schemas for request and response validation."""

import datetime

from pydantic import BaseModel, Field, field_validator


class JokeCreate(BaseModel):
    """Schema for creating a new joke."""

    text: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="The joke text",
        examples=["Chuck Norris can divide by zero."],
    )

    @field_validator("text")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        """Strip whitespace and ensure non-empty after stripping."""
        v = v.strip()
        if not v:
            raise ValueError("Joke text cannot be blank")
        return v


class JokeResponse(BaseModel):
    """Schema for a joke in API responses."""

    id: int
    text: str
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class JokeListResponse(BaseModel):
    """Paginated list of jokes."""

    jokes: list[JokeResponse]
    total: int
    page: int
    per_page: int


class APIKeyCreate(BaseModel):
    """Schema for creating a new API key."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="A descriptive name for this API key",
        examples=["my-app"],
    )


class APIKeyResponse(BaseModel):
    """Response when a new API key is created. Key shown only once."""

    name: str
    api_key: str
    message: str = "Store this key securely — it will not be shown again."


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    database: str
    timestamp: datetime.datetime


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
