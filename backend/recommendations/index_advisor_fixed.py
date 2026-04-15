"""Compatibility shim for legacy `backend.recommendations.index_advisor_fixed` imports."""

from app.recommendations.index_advisor import *  # noqa: F403

# Legacy alias expected by some tests
try:
    IndexAdvisor = RealIndexAdvisor  # type: ignore # noqa: N816
except Exception:
    pass

