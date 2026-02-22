"""Chuck Norris Jokes API — main application."""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import (
    generate_api_key,
    hash_api_key,
    verify_admin_secret,
    verify_api_key,
)
from app.database import Base, engine, get_db
from app.logging_config import setup_logging
from app.middleware import RequestLoggingMiddleware
from app.models import APIKey, Joke
from app.schemas import (
    APIKeyCreate,
    APIKeyResponse,
    ErrorResponse,
    HealthResponse,
    JokeCreate,
    JokeListResponse,
    JokeResponse,
)
from app.seed_data import SEED_JOKES

logger = setup_logging(os.getenv("LOG_LEVEL", "INFO"))

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)


# ---------------------------------------------------------------------------
# Lifespan: create tables and seed data on startup
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables and seed jokes on startup."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")

    db = next(get_db())
    try:
        existing = db.query(Joke).count()
        if existing == 0:
            for joke_text in SEED_JOKES:
                db.add(Joke(text=joke_text))
            db.commit()
            logger.info(
                "Seeded database with jokes",
                extra={"event_type": "db_seed", "joke_count": len(SEED_JOKES)},
            )
    finally:
        db.close()

    yield


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Chuck Norris Jokes API",
    description=(
        "A RESTful API serving Chuck Norris jokes. "
        "Read endpoints are public; write endpoints require an API key."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(RequestLoggingMiddleware)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/", tags=["General"])
@limiter.limit("60/minute")
def root(request: Request):
    """Welcome message with API overview."""
    # request param is required by slowapi but unused

    return {
        "message": "Welcome to the Chuck Norris Jokes API!",
        "docs": "/docs",
        "endpoints": {
            "random_joke": "GET /jokes/random",
            "joke_by_id": "GET /jokes/{id}",
            "all_jokes": "GET /jokes",
            "add_joke": "POST /jokes (requires X-API-Key)",
            "health": "GET /health",
        },
    }


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["General"],
)
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint for monitoring and CloudWatch.

    Returns database connectivity status.
    """
    try:
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    return HealthResponse(
        status="ok" if db_status == "healthy" else "degraded",
        database=db_status,
        timestamp=datetime.now(timezone.utc),
    )


@app.get(
    "/jokes/random",
    response_model=JokeResponse,
    tags=["Jokes"],
    responses={404: {"model": ErrorResponse}},
)
@limiter.limit("60/minute")
def get_random_joke(request: Request, db: Session = Depends(get_db)):
    """Return a random Chuck Norris joke."""
    joke = db.query(Joke).order_by(func.random()).first()
    if not joke:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No jokes found. Add some first!",
        )
    return joke


@app.get(
    "/jokes/{joke_id}",
    response_model=JokeResponse,
    tags=["Jokes"],
    responses={404: {"model": ErrorResponse}},
)
@limiter.limit("60/minute")
def get_joke_by_id(
    joke_id: int, request: Request, db: Session = Depends(get_db)
):
    """Return a specific joke by its ID."""
    joke = db.query(Joke).filter(Joke.id == joke_id).first()
    if not joke:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Joke with id {joke_id} not found.",
        )
    return joke


@app.get(
    "/jokes",
    response_model=JokeListResponse,
    tags=["Jokes"],
)
@limiter.limit("60/minute")
def list_jokes(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """List all jokes with pagination."""
    total = db.query(Joke).count()
    jokes = (
        db.query(Joke)
        .order_by(Joke.id)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return JokeListResponse(
        jokes=jokes, total=total, page=page, per_page=per_page
    )


@app.post(
    "/jokes",
    response_model=JokeResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Jokes"],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
@limiter.limit("10/minute")
def create_joke(
    joke: JokeCreate,
    request: Request,
    _key: APIKey = Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """Add a new Chuck Norris joke. Requires a valid API key."""
    db_joke = Joke(text=joke.text)
    try:
        db.add(db_joke)
        db.commit()
        db.refresh(db_joke)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This joke already exists.",
        )

    logger.info(
        "New joke created",
        extra={
            "event_type": "joke_created",
            "joke_id": db_joke.id,
            "api_key_id": _key.id,
        },
    )
    return db_joke


@app.post(
    "/api-keys",
    response_model=APIKeyResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Authentication"],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
@limiter.limit("5/minute")
def create_api_key(
    payload: APIKeyCreate,
    request: Request,
    _admin: str = Depends(verify_admin_secret),
    db: Session = Depends(get_db),
):
    """Generate a new API key. Requires the admin secret in X-API-Key header.

    The generated key is returned **once** — store it securely.
    """
    raw_key = generate_api_key()
    db_key = APIKey(
        key_hash=hash_api_key(raw_key),
        name=payload.name,
    )
    db.add(db_key)
    db.commit()

    logger.info(
        "New API key created",
        extra={
            "event_type": "api_key_created",
            "key_name": payload.name,
            "key_id": db_key.id,
        },
    )

    return APIKeyResponse(name=payload.name, api_key=raw_key)
