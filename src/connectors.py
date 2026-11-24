"""Explicit one-time setup; connectors themselves use standard Python imports."""

def configure_connectors(directory, *, enabled_connectors=None):
    """Register the shared location for this Python environment."""
    from zizai.core.connector_config import configure_connectors as configure
    return configure(directory, enabled_connectors=enabled_connectors)


__all__ = ['configure_connectors']
