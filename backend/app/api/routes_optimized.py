"""
Compatibility shim for older imports.

The project uses `app.api.routes` as the canonical router implementation.
Some tests/imports reference `app.api.routes_optimized`.
"""

from .routes import router

__all__ = ["router"]

