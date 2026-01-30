"""User interface components for CQViewer."""

__all__ = ["CQViewerApp", "main"]


def __getattr__(name):
    """Lazy import to avoid circular import when running as __main__."""
    if name in ("CQViewerApp", "main"):
        from .app import CQViewerApp, main
        return CQViewerApp if name == "CQViewerApp" else main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
