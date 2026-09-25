"""ASGI factory entry point: uvicorn app.main:create_app --factory."""

from app.composition import create_app

__all__ = ["create_app"]
