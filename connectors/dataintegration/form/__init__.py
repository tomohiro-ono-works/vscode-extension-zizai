"""Form support for the dataintegration connector."""
from .dataintegration_codegen import GENERATION_FIELDS, generate_dataintegration as generate

FILE_PATH_GENERATIONS = ('dataintegration.replace_fields_forrenamelist',)


def form_controls(form):
    from .ui import Controls
    return Controls(form)
