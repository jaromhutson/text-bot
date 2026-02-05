import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings, validate_settings
from app.database import init_db, close_db
from app.data.seed import seed_if_empty
from app.services.scheduler import setup_scheduler, shutdown_scheduler
from app.routers import health, admin, webhooks

# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
)
logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    validate_settings()
    await init_db()
    await seed_if_empty()
    setup_scheduler()
    logger.info("Application started")
    yield
    # Shutdown
    shutdown_scheduler()
    await close_db()
    logger.info("Application shut down")


app = FastAPI(title="Text Bot", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security headers middleware
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    return response

# Register routers
app.include_router(health.router)
app.include_router(admin.router)
app.include_router(webhooks.router)
