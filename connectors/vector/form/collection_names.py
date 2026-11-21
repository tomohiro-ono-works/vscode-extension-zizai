"""List locally available collections for the Vector form."""
from pathlib import Path
import re


_VECTOR_COLLECTION_SUFFIX = '.vector.duckdb'


def _vector_collection_names(folder):
    if not folder or not Path(folder).is_absolute():
        return []
    try:
        names = []
        for entry in Path(folder).iterdir():
            name = entry.name.removesuffix(_VECTOR_COLLECTION_SUFFIX)
            if name != entry.name and re.fullmatch(r'[\w-]+', name) and entry.is_file():
                names.append(name)
        return sorted(names, key=lambda name: (name.casefold(), name))
    except (OSError, ValueError):
        return []
