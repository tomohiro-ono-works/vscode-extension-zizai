"""Load trusted shared connectors only when their generated code is executed."""

def configure_connectors(directory):
    """Explicitly persist the shared location in user settings."""
    from zizai.core.connector_config import configure_connectors as configure
    return configure(directory)


def load_connector(module_path):
    """Import a trusted shared Python module at execution time."""
    from zizai.core.connector_loader import load_connector as load
    return load(module_path)

__all__ = ['configure_connectors', 'load_connector']
