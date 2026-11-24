"""Form support for the vector connector."""
from .vector_codegen import GENERATION_FIELDS, generate_vector as generate

DEFAULT_PATHS = {'db_folder': 'config/vector-db'}
RESET_DEFAULTS_ON_ACTION_CHANGE = ('output_variable',)
RESET_EMPTY_ON_ACTION_CHANGE = ('collection_name',)


def form_controls(form):
    from .ui import Controls
    return Controls(form)
