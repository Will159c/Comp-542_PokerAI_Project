"""Entry point: re-export the FastAPI app from ``classic_poker``."""

from classic_poker.server import app

__all__ = ["app"]
