"""Form support for Markdown slide conversion."""
from .slides_codegen import GENERATION_FIELDS, generate_slides as generate


def form_controls(form):
    from .ui import Controls
    return Controls(form)
