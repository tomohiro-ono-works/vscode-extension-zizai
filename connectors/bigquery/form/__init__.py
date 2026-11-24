"""Form support for the bigquery connector."""
from .bigquery_codegen import GENERATION_FIELDS, generate_bigquery as generate

MAGIC_NAME = 'zizai_bq'
SQL_CONNECTION = ('--project-id', 'zizai_bq_project', str)
