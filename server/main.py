"""
JobHunt — FastAPI Main Application

Entry point for the JobHunt server. Handles startup/shutdown lifecycle,
dependency injection setup, and router registration.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.config import get_settings, get_user_profile
from server.routers import webhook
from server.services.db import Database
from server.services.gmail_client import GmailClient
from server.services.llm_client import LLMClient

# Setup basic logging format.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage application startup and shutdown.

    Startup:
      1. Load settings and user profile.
      2. Set log level.
      3. Initialize database.
      4. Initialize and authenticate Gmail API (blocking!).
      5. Initialize LLM API.
      6. Store in app.state.

    Shutdown:
      1. Close LLM client.
      2. Close database.
    """
    logger.info("Starting JobHunt server...")

    settings = get_settings()
    user_profile = get_user_profile()

    # Validate configuration on startup
    user_profile.validate()

    # Adjust log level based on config.
    logging.getLogger().setLevel(settings.log_level)

    # Initialize components.
    db = Database()

    gmail_client = GmailClient(settings)
    # This might open a browser window for OAuth if no token exists!
    gmail_client.authenticate()

    llm_client = LLMClient(settings, user_profile)

    # Store globally so dependencies.py can inject them into routes.
    app.state.settings = settings
    app.state.db = db
    app.state.gmail_client = gmail_client
    app.state.llm_client = llm_client

    logger.info("Startup complete. Server is ready.")

    yield  # Application runs here

    # Shutdown sequence.
    logger.info("Shutting down JobHunt server...")
    await llm_client.close()
    db.close()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="JobHunt",
    description="HITL LinkedIn Email Drafter",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow Tampermonkey script (running on LinkedIn) to POST to this server.
# GM_xmlhttpRequest bypasses browser CORS, but this also enables curl testing
# and fallback for Tampermonkey forks that use fetch().
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://www.linkedin.com",
        "https://linkedin.com",
    ],
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["*"],
)

# Register routers
app.include_router(webhook.router)


def start() -> None:
    """Entry point for the jobhunt CLI command."""
    if len(sys.argv) > 1 and sys.argv[1] == "stats":
        from server.cli import show_stats
        show_stats()
        return

    settings = get_settings()
    uvicorn.run(
        "server.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
    )


if __name__ == "__main__":
    start()
