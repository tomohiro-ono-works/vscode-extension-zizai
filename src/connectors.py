"""Explicit one-time setup; connectors themselves use standard Python imports."""

def configure_connectors(directory):
    """Register the shared location for this Python environment."""
    from zizai.core.connector_config import configure_connectors as configure
    return configure(directory)


__all__ = ['configure_connectors']
