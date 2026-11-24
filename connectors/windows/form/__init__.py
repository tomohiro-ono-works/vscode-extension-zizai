"""Form support for the windows connector."""
from .windows_codegen import GENERATION_FIELDS, generate_windows as generate

RESET_ON_ACTION_CHANGE = ('wait_before_seconds', 'wait_after_seconds')
RESET_DEFAULTS_ON_ACTION_CHANGE = ('output_variable',)


def form_controls(form):
    from .ui import Controls
    return Controls(form)
