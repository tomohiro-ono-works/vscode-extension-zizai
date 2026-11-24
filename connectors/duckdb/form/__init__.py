"""Form support for the duckdb connector."""
from pathlib import Path

from .duckdb_codegen import GENERATION_FIELDS, generate_duckdb as generate

MAGIC_NAME = 'zizai_duck'
SQL_CONNECTION = ('--db-file', 'zizai_duck_db', (str, Path))
