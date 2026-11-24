"""Discover form support shipped by the ZizAI runtime build."""
from functools import cache
from importlib import import_module
from importlib.metadata import distributions
from importlib.util import find_spec
from pkgutil import iter_modules


@cache
def form_ids():
    identifiers = {item.name for item in iter_modules(__path__) if item.ispkg}
    if not identifiers:
        # Editable installs map the connector packages to separate source directories.
        for runtime in distributions(name='zizai-runtime'):
            identifiers.update(
                point.name for point in runtime.entry_points
                if point.group == 'zizai.connector_forms' and point.name.isidentifier()
                and find_spec(f'{__name__}.{point.name}') is not None
            )
    return tuple(sorted(identifiers))


def form_support(identifier):
    if identifier in form_ids():
        return import_module(f'{__name__}.{identifier}')
    return None


def generation_support(kind):
    support = form_support(kind.partition('.')[0])
    if kind not in getattr(support, 'GENERATION_FIELDS', {}):
        raise ValueError('generationは許可されたコネクタ操作を指定してください。')
    return support
